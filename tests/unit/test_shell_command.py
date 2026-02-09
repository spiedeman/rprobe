"""
shell_command 功能单元测试
"""
import socket
from unittest.mock import Mock, patch, call

import pytest
import paramiko

from src import SSHClient
from src.config.models import SSHConfig
from src.core.models import CommandResult


class TestOpenShellSession:
    """测试 open_shell_session 方法"""

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

    @patch('paramiko.SSHClient')
    def test_open_shell_session_success(self, mock_ssh_client_class, mock_ssh_config):
        """测试成功打开 shell 会话"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 创建 mock channel
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"\x1b[?2004hroot@test:~# "
        mock_channel.closed = False
        
        mock_transport.open_session.return_value = mock_channel
        
        prompt = client.open_shell_session()
        
        assert client.shell_session_active is True
        assert "root@test:~#" in prompt
        mock_channel.get_pty.assert_called_once()
        mock_channel.invoke_shell.assert_called_once()

    @patch('paramiko.SSHClient')
    def test_open_shell_session_already_exists(self, mock_ssh_client_class, mock_ssh_config):
        """测试会话已存在时抛出异常"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.closed = False
        mock_transport.open_session.return_value = mock_channel
        
        # 第一次打开 - 使用短超时加速测试
        client.open_shell_session(timeout=0.01)
        
        # 第二次打开应该抛出异常
        with pytest.raises(RuntimeError, match="Shell 会话已经存在"):
            client.open_shell_session(timeout=0.01)

    @patch('paramiko.SSHClient')
    def test_open_shell_session_timeout(self, mock_ssh_client_class, mock_ssh_config):
        """测试打开会话超时 - 使用默认prompt"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.closed = False
        mock_transport.open_session.return_value = mock_channel
        
        # open_shell_session 在超时时不会抛出异常，而是使用默认prompt "#"
        prompt = client.open_shell_session(timeout=0.01)
        assert prompt == "#"


class TestShellCommand:
    """测试 shell_command 方法"""

    def _setup_shell_session(self, mock_ssh_client_class, mock_ssh_config):
        """设置 shell 会话"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        
        # 打开 shell 会话
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"\x1b[?2004hroot@test:~# "
        mock_channel.closed = False
        mock_transport.open_session.return_value = mock_channel
        
        client.open_shell_session()
        return client, mock_client, mock_transport, mock_channel

    @patch('paramiko.SSHClient')
    def test_shell_command_success(self, mock_ssh_client_class, mock_ssh_config):
        """测试成功执行 shell 命令"""
        client, mock_client, mock_transport, mock_channel = self._setup_shell_session(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 模拟命令执行输出
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"ls\nfile1.txt\nfile2.txt\n\x1b[?2004hroot@test:~# "
        
        result = client.shell_command("ls")
        
        assert isinstance(result, CommandResult)
        assert "file1.txt" in result.stdout
        assert "file2.txt" in result.stdout
        assert result.exit_code == 0
        mock_channel.send.assert_called_once_with(b"ls\n")

    @patch('paramiko.SSHClient')
    def test_shell_command_no_session(self, mock_ssh_client_class, mock_ssh_config):
        """测试没有会话时抛出异常"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        # 不打开 shell 会话
        
        with pytest.raises(RuntimeError, match="没有活动的 Shell 会话"):
            client.shell_command("ls")

    @patch('paramiko.SSHClient')
    def test_shell_command_with_ansi_codes(self, mock_ssh_client_class, mock_ssh_config):
        """测试清理 ANSI 控制字符"""
        client, mock_client, mock_transport, mock_channel = self._setup_shell_session(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 包含 ANSI 控制字符的输出
        # 格式: 命令回显 + 输出内容 + prompt
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"ls\n\x1b[34mfile1\x1b[0m\n\x1b[?2004hroot@test:~# "
        
        result = client.shell_command("ls")
        
        # ANSI 代码应该被清理
        assert "\x1b[" not in result.stdout
        # 第一行（命令回显）应该被移除
        assert "file1" in result.stdout

    @patch('paramiko.SSHClient')
    def test_shell_command_socket_error(self, mock_ssh_client_class, mock_ssh_config):
        """测试 socket 错误处理"""
        client, mock_client, mock_transport, mock_channel = self._setup_shell_session(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 使用 side_effect 列表确保多次调用都有返回值
        mock_channel.recv_ready.side_effect = [True, True, True]
        mock_channel.recv.side_effect = socket.error("Connection reset")
        
        with pytest.raises((ConnectionError, Exception)):
            client.shell_command("command")


class TestCloseShellSession:
    """测试 close_shell_session 方法"""

    @patch('paramiko.SSHClient')
    def test_close_shell_session(self, mock_ssh_client_class, mock_ssh_config):
        """测试关闭 shell 会话"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        
        # 先打开会话 - 使用短超时加速测试
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.closed = False
        mock_transport.open_session.return_value = mock_channel
        
        client.open_shell_session(timeout=0.01)
        assert client.shell_session_active is True
        
        # 关闭会话
        client.close_shell_session()
        assert client.shell_session_active is False
        mock_channel.close.assert_called_once()

    @patch('paramiko.SSHClient')
    def test_close_shell_session_no_active_session(self, mock_ssh_client_class, mock_ssh_config):
        """测试关闭不存在的会话"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        
        # 不应该抛出异常
        client.close_shell_session()
        assert client.shell_session_active is False
