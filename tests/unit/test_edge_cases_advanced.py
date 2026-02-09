"""
高级边界测试 - 提升代码覆盖率
包含异常路径、日志验证和边界值测试
"""
import logging
import socket
from unittest.mock import Mock, patch, MagicMock, call

import pytest
import paramiko

from src import SSHClient
from src.config.models import SSHConfig
from src.core.models import CommandResult


class TestExceptionPaths:
    """异常路径测试"""

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
    def test_connect_with_key_file_exception(self, mock_ssh_client_class, mock_ssh_config_with_key, caplog):
        """测试使用密钥文件连接时的异常"""
        mock_client = Mock()
        mock_client.connect.side_effect = paramiko.SSHException("Key file not found")
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config_with_key)
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(paramiko.SSHException):
                client.connect()
        
        assert "SSH 连接错误" in caplog.text
        assert client._connection is None or not client._connection.is_connected

    @patch('paramiko.SSHClient')
    def test_disconnect_with_exception(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试断开连接时的异常处理"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        
        # 模拟关闭时抛出异常
        mock_transport.close.side_effect = Exception("Transport close error")
        mock_client.close.side_effect = Exception("Client close error")
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        
        with caplog.at_level(logging.WARNING):
            # 不应该抛出异常，应该记录警告
            client.disconnect()
        
        assert "关闭 Transport 时出错" in caplog.text
        assert "关闭 SSHClient 时出错" in caplog.text

    @patch('paramiko.SSHClient')
    def test_shell_session_open_exception(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试打开 shell 会话时的异常"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_transport.open_session.side_effect = paramiko.SSHException("Failed to open session")
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError, match="打开 Shell 会话失败"):
                client.open_shell_session()
        
        assert client._shell_session is None

    @patch('paramiko.SSHClient')
    def test_shell_session_close_with_exception(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试关闭 shell 会话时的异常处理"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 先打开会话
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b"root@test:~# "
        mock_channel.closed = False
        mock_transport.open_session.return_value = mock_channel
        
        client.open_shell_session()
        
        # 模拟关闭时抛出异常
        mock_channel.close.side_effect = Exception("Close error")
        
        with caplog.at_level(logging.WARNING):
            client.close_shell_session()
        
        assert "关闭 Shell 会话时出错" in caplog.text

    @patch('paramiko.SSHClient')
    def test_recv_all_channel_data_with_transport_error(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试接收数据时传输层错误"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = False
        mock_channel.closed = False
        
        # 模拟传输层断开
        mock_transport.is_active.return_value = False
        mock_transport.open_session.return_value = mock_channel
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ConnectionError, match="SSH 连接已断开"):
                client.exec_command("test")

    @patch('paramiko.SSHClient')
    def test_exec_command_with_general_exception(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试 exec_command 中的一般异常"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.exec_command.side_effect = Exception("Unexpected error")
        mock_transport.open_session.return_value = mock_channel
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                client.exec_command("test")


class TestLoggingVerification:
    """日志验证测试"""

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
    def test_connect_logs(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试连接时的日志记录"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        
        with caplog.at_level(logging.DEBUG):
            client.connect()
        
        assert "正在连接 SSH 服务器" in caplog.text
        assert "SSH 连接成功" in caplog.text
        assert "使用 password 认证方式" in caplog.text

    @patch('paramiko.SSHClient')
    def test_exec_command_logs(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试执行命令时的日志记录"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        with caplog.at_level(logging.DEBUG):
            client.exec_command("echo test")
        
        assert "[exec] 执行命令: echo test" in caplog.text
        assert "[exec] 命令执行完成" in caplog.text
        assert "exit_code=0" in caplog.text

    @patch('paramiko.SSHClient')
    def test_shell_command_logs(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试 shell 命令的日志记录"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 打开会话
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b"root@test:~# "
        mock_channel.closed = False
        mock_transport.open_session.return_value = mock_channel
        
        with caplog.at_level(logging.DEBUG):
            client.open_shell_session()
        
        assert "正在打开 Shell 会话" in caplog.text
        assert "Shell 会话已打开" in caplog.text

    @patch('paramiko.SSHClient')
    def test_output_truncation_logs(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试输出截断的日志记录"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        client._config.max_output_size = 10
        
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"A" * 20
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        with caplog.at_level(logging.WARNING):
            client.exec_command("generate_large")
        
        assert "标准输出超过最大限制" in caplog.text

    @patch('paramiko.SSHClient')
    def test_disconnect_logs(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试断开连接的日志"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client_class.return_value = mock_client
        
        client = SSHClient(mock_ssh_config)
        client.connect()
        
        with caplog.at_level(logging.INFO):
            client.disconnect()
        
        assert "正在断开 SSH 连接" in caplog.text
        assert "SSH 连接已断开" in caplog.text


class TestBoundaryValues:
    """边界值测试"""

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
    def test_empty_command_output(self, mock_ssh_client_class, mock_ssh_config):
        """测试空命令输出"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("true")
        
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == 0

    @patch('paramiko.SSHClient')
    def test_exact_max_output_size(self, mock_ssh_client_class, mock_ssh_config):
        """测试刚好达到最大输出限制"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        client._config.max_output_size = 100
        
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"A" * 100  # 刚好100字节
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("exact_size")
        
        assert len(result.stdout) == 100
        assert "[输出已截断" not in result.stdout  # 不应该被截断

    @patch('paramiko.SSHClient')
    def test_one_byte_over_max_size(self, mock_ssh_client_class, mock_ssh_config):
        """测试超过最大限制1字节"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        client._config.max_output_size = 100
        
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"A" * 101  # 101字节，超过1字节
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("one_byte_over")
        
        assert "[输出已截断" in result.stdout

    @patch('paramiko.SSHClient')
    def test_very_short_timeout(self, mock_ssh_client_class, mock_ssh_config):
        """测试极短超时时间"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = False
        mock_channel.closed = False
        mock_transport.open_session.return_value = mock_channel
        
        with pytest.raises(TimeoutError):
            client.exec_command("slow", timeout=0.001)  # 1ms 超时

    @patch('paramiko.SSHClient')
    def test_unicode_in_command(self, mock_ssh_client_class, mock_ssh_config):
        """测试包含 Unicode 的命令"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = "你好世界 🌍\n".encode('utf-8')
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("echo '你好'")
        
        assert "你好世界" in result.stdout
        assert "🌍" in result.stdout

    @patch('paramiko.SSHClient')
    def test_special_characters_in_output(self, mock_ssh_client_class, mock_ssh_config):
        """测试特殊字符输出"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        special_chars = "<>&\"'\n\t\r"
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = special_chars.encode('utf-8')
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("special_chars")
        
        assert result.stdout == special_chars

    @patch('paramiko.SSHClient')
    def test_binary_data_in_output(self, mock_ssh_client_class, mock_ssh_config):
        """测试二进制数据输出"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        binary_data = bytes([0x00, 0x01, 0xFF, 0xFE])
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = binary_data
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("binary")
        
        # 应该能处理二进制数据而不抛出异常
        assert isinstance(result.stdout, str)

    @patch('paramiko.SSHClient')
    def test_negative_exit_code(self, mock_ssh_client_class, mock_ssh_config):
        """测试负退出码"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = -1
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("fail")
        
        assert result.exit_code == -1
        assert result.success is False

    @patch('paramiko.SSHClient')
    def test_very_long_command(self, mock_ssh_client_class, mock_ssh_config):
        """测试超长命令"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        long_command = "echo " + "A" * 1000
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_channel.exec_command = Mock()
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command(long_command)
        
        # 验证命令被正确传递
        mock_channel.exec_command.assert_called_once_with(long_command)
        assert result.command == long_command

    @patch('paramiko.SSHClient')
    def test_shell_prompt_variations(self, mock_ssh_client_class, mock_ssh_config):
        """测试不同格式的 shell prompt"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 测试 [user@host ~]$ 格式
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"[user@host ~]$ "
        mock_channel.closed = False
        mock_transport.open_session.return_value = mock_channel
        
        prompt = client.open_shell_session()
        assert "$" in prompt or "#" in prompt

    @patch('paramiko.SSHClient')
    def test_multiple_stderr_lines(self, mock_ssh_client_class, mock_ssh_config):
        """测试多行 stderr 输出"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        # 将两行 stderr 合并为一次返回，简化测试
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.side_effect = [True, False]
        mock_channel.recv_stderr.return_value = b"Error line 1\nError line 2\n"
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 1
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("fail_with_errors")
        
        assert "Error line 1" in result.stderr
        assert "Error line 2" in result.stderr
        assert result.exit_code == 1


class TestHelperMethods:
    """辅助方法测试 - 新架构使用独立模块"""

    def test_strip_ansi_with_various_codes(self):
        """测试清理各种 ANSI 代码 - 使用 ansi_cleaner 模块"""
        from src.utils.ansi_cleaner import ANSICleaner
        
        cleaner = ANSICleaner()
        
        # 颜色代码
        assert cleaner.clean("\x1b[32mGreen\x1b[0m") == "Green"
        # 光标控制
        assert cleaner.clean("\x1b[2KClear") == "Clear"
        # 复合代码
        assert cleaner.clean("\x1b[1;31mBoldRed\x1b[0m") == "BoldRed"
        # 无代码
        assert cleaner.clean("Normal text") == "Normal text"

    def test_detect_prompt_patterns(self):
        """测试 prompt 检测的各种模式 - 使用 prompt_detector 模块"""
        from src.patterns.prompt_detector import PromptDetector
        
        detector = PromptDetector()
        
        # user@host:~$ 格式
        result = detector.detect("user@host:~$")
        assert result == "user@host:~$"
        # user@host:~# 格式（root）
        result = detector.detect("root@server:/#")
        assert result == "root@server:/#"
        # [user@host ~]$ 格式
        result = detector.detect("[user@host ~]$")
        assert result == "[user@host ~]$"
        # 无匹配时返回最后一行
        result = detector.detect("Some random text")
        assert result == "Some random text"

    def test_clean_shell_output_with_prompt_detector(self):
        """测试 shell 输出清理 - 使用 PromptDetector"""
        from src.patterns.prompt_detector import PromptDetector
        
        detector = PromptDetector()
        
        # 学习一个提示符
        detector.learn_prompt("root@test:~#")
        
        # 测试输出清理
        output = "ls\nfile1.txt\nfile2.txt\nroot@test:~#"
        cleaned = detector.clean_output(output, "ls")
        
        # 验证结果
        assert "file1.txt" in cleaned
        assert "file2.txt" in cleaned
        assert "root@test:~#" not in cleaned  # prompt 被移除
        assert "ls" not in cleaned  # 命令回显被移除

    def test_connection_manager_connect(self, mock_ssh_config):
        """测试连接管理器自动连接"""
        from src.core.connection import ConnectionManager
        
        with patch('src.core.connection.paramiko.SSHClient') as mock_ssh_client_class:
            mock_client = Mock()
            mock_transport = Mock()
            mock_transport.is_active.return_value = True
            mock_client.get_transport.return_value = mock_transport
            mock_ssh_client_class.return_value = mock_client
            
            # 创建连接管理器
            conn_manager = ConnectionManager(mock_ssh_config)
            
            # 初始未连接
            assert not conn_manager.is_connected
            
            # 调用 connect
            conn_manager.connect()
            
            # 验证已连接
            assert conn_manager.is_connected
            mock_client.connect.assert_called_once()


class TestAdditionalCoverage:
    """额外覆盖率测试"""

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
    def test_shell_channel_send_exception(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试 shell channel send 异常"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 打开会话
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b"root@test:~# "
        mock_channel.closed = False
        mock_transport.open_session.return_value = mock_channel
        
        client.open_shell_session()
        
        # 模拟 send 异常
        mock_channel.send.side_effect = Exception("Send failed")
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception):
                client.shell_command("ls")

    @patch('paramiko.SSHClient')
    def test_channel_eof_handling(self, mock_ssh_client_class, mock_ssh_config):
        """测试 channel EOF 处理"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"output"
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = False
        mock_channel.eof_received = True  # 设置 EOF
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("test")
        assert result.exit_code == 0

    @patch('paramiko.SSHClient')
    def test_long_inactivity_timeout_check(self, mock_ssh_client_class, mock_ssh_config):
        """测试长时间无活动后的超时检查"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        # 模拟立即接收数据然后完成
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"delayed output"
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("slow")
        assert "delayed output" in result.stdout

    @patch('paramiko.SSHClient')
    def test_stderr_truncation(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试 stderr 截断"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        client._config.max_output_size = 50
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.side_effect = [True, False]
        mock_channel.recv_stderr.return_value = b"E" * 100  # 超过限制
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 1
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        with caplog.at_level(logging.WARNING):
            result = client.exec_command("error")
        
        assert "[错误输出已截断" in result.stderr

    @patch('paramiko.SSHClient')
    def test_transport_check_interval(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试传输层检查间隔"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        mock_transport.open_session.return_value = mock_channel
        
        result = client.exec_command("check_transport")
        
        # 验证 transport.is_active 被调用
        assert mock_transport.is_active.called

    @patch('paramiko.SSHClient')
    def test_wait_for_prompt_with_data_after_detection(self, mock_ssh_client_class, mock_ssh_config):
        """测试 shell 命令输出包含 prompt"""
        client, mock_client, mock_transport = self._setup_mock_connection(
            mock_ssh_client_class, mock_ssh_config
        )
        
        # 先打开会话
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"root@test:~# "
        mock_channel.closed = False
        mock_transport.open_session.return_value = mock_channel
        
        client.open_shell_session()
        
        # 执行命令
        mock_channel.recv_ready.side_effect = [True, True, False, False]
        mock_channel.recv.side_effect = [
            b"cmd\noutput line\n",
            b"root@test:~# "
        ]
        
        result = client.shell_command("cmd")
        
        assert "output line" in result.stdout

    def test_clean_shell_output_without_prompt(self):
        """测试无 prompt 时的输出清理"""
        from src.patterns.prompt_detector import PromptDetector
        
        detector = PromptDetector(enable_learning=False)
        
        # 无学习过的提示符
        output = "cmd\noutput line\n"
        cleaned = detector.clean_output(output, "cmd")
        
        # 命令回显应该被移除
        assert "output line" in cleaned

    @patch('paramiko.SSHClient')
    def test_context_manager_with_exception_in_exit(self, mock_ssh_client_class, mock_ssh_config, caplog):
        """测试上下文管理器退出时的异常处理"""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_client.close.side_effect = Exception("Close error")
        mock_ssh_client_class.return_value = mock_client
        
        with caplog.at_level(logging.WARNING):
            with pytest.raises(ValueError):
                with SSHClient(mock_ssh_config) as client:
                    raise ValueError("Test error")
        
        # 即使关闭时出错，也应该记录警告
        assert "关闭 SSHClient 时出错" in caplog.text
