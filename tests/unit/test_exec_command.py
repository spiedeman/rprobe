"""
exec_command 功能单元测试
"""
import socket
from unittest.mock import Mock, patch, MagicMock

import pytest
import paramiko

from src import SSHClient
from src.config.models import SSHConfig
from src.core.models import CommandResult


class TestExecCommand:
    """测试 exec_command 方法"""

    def _setup_mock_connection(self, mock_ssh_client_class, mock_ssh_config):
        """设置模拟连接"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        return client, mock_client, mock_transport

    @patch('src.backends.paramiko_backend.paramiko.SSHClient')
    def test_exec_command_success(self, mock_ssh_client_class, mock_ssh_config):
        """测试成功执行命令"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 创建 mock channel
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"Hello World\n"
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_channel.eof_received = True
        
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("echo 'Hello World'")
        
        assert isinstance(result, CommandResult)
        assert result.stdout == "Hello World\n"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.success is True
        assert result.command == "echo 'Hello World'"

    @patch('src.backends.paramiko_backend.paramiko.SSHClient')
    def test_exec_command_with_stderr(self, mock_ssh_client_class, mock_ssh_config):
        """测试命令输出 stderr"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b""
        mock_channel.recv_stderr_ready.side_effect = [True, False]
        mock_channel.recv_stderr.return_value = b"Error message\n"
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 1
        mock_channel.closed = True
        
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("invalid_command")
        
        assert result.exit_code == 1
        assert result.stderr == "Error message\n"
        assert result.success is False

    @patch('src.backends.paramiko_backend.paramiko.SSHClient')
    def test_exec_command_timeout(self, mock_ssh_client_class, mock_ssh_config):
        """测试命令执行超时"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = False
        mock_channel.closed = False
        
        mock_transport.open_session.return_value = mock_channel
        
        # 使用很短的超时时间
        with pytest.raises(TimeoutError):
            client.exec_command("sleep 10", timeout=0.1)

    @patch('src.backends.paramiko_backend.paramiko.SSHClient')
    def test_exec_command_connection_lost(self, mock_ssh_client_class, mock_ssh_config):
        """测试执行过程中连接断开"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = False
        mock_channel.closed = False
        
        # 模拟连接断开
        mock_transport.is_active.side_effect = [True, False]
        mock_transport.open_session.return_value = mock_channel
        
        with pytest.raises(ConnectionError):
            client.exec_command("some_command")

    @patch('src.backends.paramiko_backend.paramiko.SSHClient')
    def test_exec_command_large_output_truncation(self, mock_ssh_client_class, mock_ssh_config):
        """测试大输出自动截断"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 设置很小的输出限制
        client._config.max_output_size = 100
        
        mock_channel = Mock()
        # 模拟数据流：
        # 第一次调用 recv_ready: True，返回50字节
        # 第二次调用 recv_ready: True，返回100字节（触发截断）
        # 之后：False（没有更多数据）
        # 注意：每次循环中 _recv_channel_data 会调用两次 recv_ready（stdout和stderr）
        mock_channel.recv_ready.side_effect = [True, False, True, False, False, False]
        mock_channel.recv.side_effect = [b"A" * 50, b"B" * 100]
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        # channel在数据读取后才关闭
        mock_channel.closed = False
        mock_channel.eof_received = True
        
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("generate_large_output")
        
        # 检查截断是否发生：
        # - 第一块50字节被接收
        # - 第二块100字节被接收，但总长度达到150>100，需要截断到100字节
        # - 最终结果应该是100字节 + 截断提示
        assert len(result.stdout) <= 120  # 100 + 截断提示（约20个字符）
        # 由于截断逻辑，我们应该能看到截断提示，或者至少数据被截断了

    @patch('src.backends.paramiko_backend.paramiko.SSHClient')
    def test_exec_command_socket_timeout(self, mock_ssh_client_class, mock_ssh_config):
        """测试 socket 超时处理"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.side_effect = socket.timeout("Timeout")
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        mock_transport.open_session.return_value = mock_channel
        
        # socket.timeout 应该被捕获并继续等待
        result = client.exec_command("slow_command")
        
        assert result.exit_code == 0

    @patch('src.backends.paramiko_backend.paramiko.SSHClient')
    def test_exec_command_socket_error(self, mock_ssh_client_class, mock_ssh_config):
        """测试 socket 错误处理"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.side_effect = socket.error("Connection reset")
        mock_channel.recv_stderr_ready.return_value = False
        
        mock_transport.open_session.return_value = mock_channel
        
        with pytest.raises(ConnectionError):
            client.exec_command("command")

    @patch('src.backends.paramiko_backend.paramiko.SSHClient')
    def test_exec_command_channel_closed_with_buffered_data(self, mock_ssh_client_class, mock_ssh_config):
        """测试 channel 关闭但有缓冲数据的情况"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        # 模拟 channel 关闭但仍有数据
        # 需要确保两次数据读取都完成后再退出
        # 模式：连续两次 True(读取数据), 然后 False(退出循环)
        mock_channel.recv_ready.side_effect = [True, True, False, False, False, False]
        mock_channel.recv.side_effect = [b"First part\n", b"Second part\n"]
        mock_channel.recv_stderr_ready.return_value = False
        # 延迟 exit_status_ready 返回 True，确保数据先被读取
        mock_channel.exit_status_ready.side_effect = [False, False, True]
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = False
        mock_channel.eof_received = True
        
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("command")
        
        assert "First part" in result.stdout
        assert "Second part" in result.stdout

    @patch('src.backends.paramiko_backend.paramiko.SSHClient')
    def test_exec_command_without_connection(self, mock_ssh_client_class, mock_ssh_config):
        """测试未连接时自动连接"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        # 不手动连接
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        mock_transport.open_session.return_value = mock_channel
        
        # 应该自动连接
        result = client.exec_command("echo test")
        
        mock_client.connect.assert_called_once()
        assert result.exit_code == 0
