"""
Channel Receiver 模块简化补充测试
"""

import socket
from unittest.mock import Mock

import pytest

from src.receivers import ChannelDataReceiver
from src.config.models import SSHConfig


class TestRecvOnceExtended:
    """recv_once 扩展测试"""

    def test_recv_once_no_data_ready(self):
        """测试数据未就绪"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False

        data, truncated = receiver.recv_once(mock_channel, is_stderr=False, current_size=0)

        assert data == b""
        assert truncated is False

    def test_recv_once_empty_bytes(self):
        """测试接收到空bytes"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b""

        data, truncated = receiver.recv_once(mock_channel, is_stderr=False, current_size=0)

        assert data == b""
        assert truncated is False

    def test_recv_once_exact_at_limit(self):
        """测试恰好达到限制"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", max_output_size=100
        )
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b"x" * 100

        data, truncated = receiver.recv_once(mock_channel, is_stderr=False, current_size=0)

        assert len(data) == 100
        assert truncated is False

    def test_recv_once_partial_truncation(self):
        """测试部分截断"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", max_output_size=100
        )
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b"x" * 50

        data, truncated = receiver.recv_once(mock_channel, is_stderr=False, current_size=80)

        assert len(data) == 20  # 只允许20字节
        assert truncated is True

    def test_recv_once_zero_allowed(self):
        """测试允许0字节时的截断"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", max_output_size=100
        )
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b"x" * 50

        data, truncated = receiver.recv_once(mock_channel, is_stderr=False, current_size=100)

        assert data == b""
        assert truncated is True

    def test_recv_once_stderr_path(self):
        """测试stderr路径"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_stderr_ready.return_value = True
        mock_channel.recv_stderr.return_value = b"error output"

        data, truncated = receiver.recv_once(mock_channel, is_stderr=True, current_size=0)

        assert data == b"error output"
        assert truncated is False

    def test_recv_once_socket_error(self):
        """测试socket错误"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.side_effect = socket.error("Connection reset")

        with pytest.raises(ConnectionError) as exc_info:
            receiver.recv_once(mock_channel, is_stderr=False, current_size=0)

        assert "网络连接错误" in str(exc_info.value)


class TestRecvAllExtended:
    """recv_all 扩展测试"""

    def test_recv_all_with_both_outputs(self):
        """测试同时接收stdout和stderr"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"stdout data"
        mock_channel.recv_stderr_ready.side_effect = [True, False]
        mock_channel.recv_stderr.return_value = b"stderr data"
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True

        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)

        assert exit_code == 0
        assert "stdout" in stdout
        assert "stderr" in stderr

    def test_recv_all_transport_disconnect(self):
        """测试传输层断开"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b"some data"

        mock_transport = Mock()
        mock_transport.is_active.return_value = False

        with pytest.raises(ConnectionError) as exc_info:
            receiver.recv_all(mock_channel, timeout=0.1, transport=mock_transport)

        assert "SSH 连接已断开" in str(exc_info.value)

    def test_recv_all_with_exit_code(self):
        """测试获取exit code"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 42
        mock_channel.closed = True

        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)

        assert exit_code == 42

    def test_recv_all_uses_config_timeout(self):
        """测试使用配置的超时"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", command_timeout=0.01
        )
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready = False
        mock_channel.closed = False

        with pytest.raises(TimeoutError):
            receiver.recv_all(mock_channel)  # 不传timeout，使用config的

    def test_recv_all_uses_config_encoding(self):
        """测试使用配置的编码"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            encoding="utf-8",
            command_timeout=0.1,
        )
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]  # 只返回一次数据
        mock_channel.recv.return_value = "你好".encode("utf-8")
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True

        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)

        assert exit_code == 0
        assert "你好" in stdout

    def test_recv_all_with_truncation(self):
        """测试数据截断"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            max_output_size=10,
            command_timeout=0.1,
        )
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]  # 只返回一次数据
        mock_channel.recv.return_value = b"x" * 20
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True

        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)

        assert exit_code == 0
        assert "截断" in stdout
