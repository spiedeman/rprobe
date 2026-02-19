"""
SSH后端测试
测试后端抽象层和ParamikoBackend实现
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.backends import (
    BackendFactory,
    AuthenticationError,
    SSHException,
    ConnectionError,
    ChannelException,
)

# 尝试导入ParamikoBackend，可能不可用
try:
    from src.backends.paramiko_backend import ParamikoBackend

    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False


class TestBackendFactory:
    """测试后端工厂"""

    def test_factory_creates_default_backend(self):
        """测试工厂创建默认后端"""
        backend = BackendFactory.create()
        assert backend is not None

    def test_factory_lists_backends(self):
        """测试列出可用后端"""
        backends = BackendFactory.list_backends()
        assert "paramiko" in backends

    def test_factory_raises_on_unknown_backend(self):
        """测试未知后端抛出异常"""
        with pytest.raises(ValueError, match="未知后端"):
            BackendFactory.create("unknown_backend")


@pytest.mark.skipif(not PARAMIKO_AVAILABLE, reason="paramiko not available")
class TestParamikoBackend:
    """测试ParamikoBackend"""

    @patch("src.backends.paramiko_backend.paramiko.SSHClient")
    def test_connect_success(self, mock_client_class):
        """测试成功连接"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_client_class.return_value = mock_client

        backend = ParamikoBackend()
        backend.connect("example.com", 22, "user", password="pass")

        assert backend.is_connected()
        mock_client.connect.assert_called_once()

    @patch("src.backends.paramiko_backend.paramiko.SSHClient")
    def test_connect_authentication_failure(self, mock_client_class):
        """测试认证失败"""
        import paramiko

        mock_client = Mock()
        mock_client.connect.side_effect = paramiko.AuthenticationException("Auth failed")
        mock_client_class.return_value = mock_client

        backend = ParamikoBackend()
        with pytest.raises(AuthenticationError):
            backend.connect("example.com", 22, "user", password="wrong")

        assert not backend.is_connected()

    @patch("src.backends.paramiko_backend.paramiko.SSHClient")
    def test_connect_ssh_exception(self, mock_client_class):
        """测试SSH异常"""
        import paramiko

        mock_client = Mock()
        mock_client.connect.side_effect = paramiko.SSHException("SSH error")
        mock_client_class.return_value = mock_client

        backend = ParamikoBackend()
        with pytest.raises(SSHException):
            backend.connect("example.com", 22, "user", password="pass")

    @patch("src.backends.paramiko_backend.paramiko.SSHClient")
    def test_disconnect(self, mock_client_class):
        """测试断开连接"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_client_class.return_value = mock_client

        backend = ParamikoBackend()
        backend.connect("example.com", 22, "user", password="pass")
        backend.disconnect()

        assert not backend.is_connected()
        mock_client.close.assert_called_once()

    @patch("src.backends.paramiko_backend.paramiko.SSHClient")
    def test_open_channel(self, mock_client_class):
        """测试打开通道"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.is_active.return_value = True
        mock_transport.open_session.return_value = mock_channel
        mock_client.get_transport.return_value = mock_transport
        mock_client_class.return_value = mock_client

        backend = ParamikoBackend()
        backend.connect("example.com", 22, "user", password="pass")
        channel = backend.open_channel()

        assert channel is not None
        mock_transport.open_session.assert_called_once()


class TestExceptions:
    """测试自定义异常"""

    def test_authentication_error(self):
        """测试认证错误异常"""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("认证失败")

    def test_connection_error(self):
        """测试连接错误异常"""
        with pytest.raises(ConnectionError):
            raise ConnectionError("连接失败")

    def test_ssh_exception(self):
        """测试SSH异常"""
        with pytest.raises(SSHException):
            raise SSHException("SSH错误")

    def test_channel_exception(self):
        """测试通道异常"""
        with pytest.raises(ChannelException):
            raise ChannelException("通道错误")
