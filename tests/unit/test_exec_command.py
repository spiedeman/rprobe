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
        # 先让 recv_ready 返回 True 以进入循环，之后再返回 False
        mock_channel.recv_ready.side_effect = [True] + [False] * 100
        mock_channel.recv.return_value = b"test"
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = False
        mock_channel.closed = False
        
        # 模拟连接断开 - 前几次返回 True，之后返回 False
        call_count = [0]
        def is_active_side_effect(*args, **kwargs):
            call_count[0] += 1
            return call_count[0] < 3
        
        mock_transport.is_active.side_effect = is_active_side_effect
        mock_transport.open_session.return_value = mock_channel
        
        with pytest.raises((ConnectionError, TimeoutError)):
            client.exec_command("some_command", timeout=0.5)

    @patch('src.backends.paramiko_backend.paramiko.SSHClient')
    def test_exec_command_large_output_truncation(self, mock_ssh_client_class, mock_ssh_config):
        """测试大输出自动截断"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 设置很小的输出限制
        client._config.max_output_size = 100
        
        mock_channel = Mock()
        # 使用 generator 提供足够的返回值
        recv_ready_count = [0]
        def recv_ready_generator(*args, **kwargs):
            recv_ready_count[0] += 1
            # 前两次返回 True（发送数据），之后返回 False
            return recv_ready_count[0] <= 2
        
        mock_channel.recv_ready.side_effect = recv_ready_generator
        
        recv_count = [0]
        def recv_generator(*args, **kwargs):
            recv_count[0] += 1
            if recv_count[0] == 1:
                return b"A" * 50  # 第一块50字节
            else:
                return b"B" * 100  # 第二块100字节，触发截断
        
        mock_channel.recv.side_effect = recv_generator
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
        # 使用 generator 确保有足够的数据读取
        recv_ready_count = [0]
        def recv_ready_generator(*args, **kwargs):
            recv_ready_count[0] += 1
            # 前两次返回 True 读取数据，之后返回 False
            return recv_ready_count[0] <= 2
        
        mock_channel.recv_ready.side_effect = recv_ready_generator
        
        recv_count = [0]
        recv_data = [b"First part\n", b"Second part\n"]
        def recv_generator(*args, **kwargs):
            recv_count[0] += 1
            if recv_count[0] <= len(recv_data):
                return recv_data[recv_count[0] - 1]
            return b""
        
        mock_channel.recv.side_effect = recv_generator
        mock_channel.recv_stderr_ready.return_value = False
        # 延迟 exit_status_ready 返回 True，确保数据先被读取
        exit_status_count = [0]
        def exit_status_generator(*args, **kwargs):
            exit_status_count[0] += 1
            return exit_status_count[0] >= 3  # 第三次调用时返回 True
        
        mock_channel.exit_status_ready.side_effect = exit_status_generator
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
