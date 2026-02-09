"""
SSHClient 核心功能单元测试
"""
import socket
from unittest.mock import Mock, patch, MagicMock

import pytest
import paramiko

from src import SSHClient
from src.config.models import SSHConfig


class TestSSHClientInit:
    """测试 SSHClient 初始化"""

    def test_init_with_config(self, mock_ssh_config):
        """测试使用配置初始化（不使用连接池）"""
        client = SSHClient(mock_ssh_config, use_pool=False)
        
        assert client._config == mock_ssh_config
        assert client._pool is None
        assert client._connection is not None
        assert client._shell_session is None
        assert not client._use_pool

    def test_init_with_pool(self, mock_ssh_config):
        """测试使用连接池初始化"""
        client = SSHClient(mock_ssh_config, use_pool=True)
        
        assert client._config == mock_ssh_config
        assert client._pool is not None
        assert client._connection is None
        assert client._shell_session is None
        assert client._use_pool is True


class TestSSHClientConnection:
    """测试 SSHClient 连接管理"""

    @patch('paramiko.SSHClient')
    def test_connect_success(self, mock_ssh_client_class, mock_ssh_config):
        """测试成功连接"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        
        assert client.is_connected is True
        mock_client.connect.assert_called_once()
        mock_client.set_missing_host_key_policy.assert_called_once()

    @patch('src.core.connection.paramiko.SSHClient')
    def test_connect_authentication_failure(self, mock_ssh_client_class, mock_ssh_config):
        """测试认证失败"""
        mock_client = Mock()
        mock_client.connect.side_effect = paramiko.AuthenticationException("Auth failed")
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config, use_pool=False)
        
        with pytest.raises(paramiko.AuthenticationException):
            client.connect()
        
        # 认证失败时连接应该断开
        assert client.is_connected is False

    @patch('paramiko.SSHClient')
    def test_connect_ssh_exception(self, mock_ssh_client_class, mock_ssh_config):
        """测试 SSH 连接异常"""
        mock_client = Mock()
        mock_client.connect.side_effect = paramiko.SSHException("Connection failed")
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        
        with pytest.raises(paramiko.SSHException):
            client.connect()

    @patch('paramiko.SSHClient')
    def test_connect_already_connected(self, mock_ssh_client_class, mock_ssh_config):
        """测试已连接时不再重复连接"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        client.connect()  # 第二次连接
        
        # 应该只调用一次 connect
        mock_client.connect.assert_called_once()

    @patch('paramiko.SSHClient')
    def test_disconnect(self, mock_ssh_client_class, mock_ssh_config):
        """测试断开连接"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        client.disconnect()
        
        mock_client.close.assert_called_once()
        mock_transport.close.assert_called_once()
        assert client.is_connected is False

    def test_is_connected_false_when_not_connected(self, mock_ssh_config):
        """测试未连接时返回 False"""
        client = SSHClient(mock_ssh_config)
        assert client.is_connected is False

    @patch('paramiko.SSHClient')
    def test_is_connected_checks_transport(self, mock_ssh_client_class, mock_ssh_config):
        """测试 is_connected 检查 transport 状态"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = False
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        
        assert client.is_connected is False


class TestSSHClientContextManager:
    """测试上下文管理器"""

    @patch('paramiko.SSHClient')
    def test_context_manager_connects_and_disconnects(self, mock_ssh_client_class, mock_ssh_config):
        """测试上下文管理器自动连接和断开"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        with SSHClient(mock_ssh_config) as client:
            assert client.is_connected is True
            mock_client.connect.assert_called_once()
        
        mock_client.close.assert_called_once()

    @patch('paramiko.SSHClient')
    def test_context_manager_handles_exception(self, mock_ssh_client_class, mock_ssh_config):
        """测试上下文管理器在异常时正确断开"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        with pytest.raises(ValueError):
            with SSHClient(mock_ssh_config) as client:
                raise ValueError("Test error")
        
        mock_client.close.assert_called_once()


class TestSSHSessions:
    """测试 SSH 会话管理"""

    @patch('src.core.client.ShellSession')
    def test_shell_session_active(self, mock_session_class, mock_ssh_config):
        """测试 shell 会话状态"""
        mock_session = Mock()
        mock_session.is_active = True
        mock_session_class.return_value = mock_session
        
        client = SSHClient(mock_ssh_config, use_pool=False)
        
        # 初始状态
        assert client.shell_session_active is False
        
        # 模拟打开会话
        client._shell_session = mock_session
        assert client.shell_session_active is True
        
        # 模拟关闭会话
        mock_session.is_active = False
        assert client.shell_session_active is False
