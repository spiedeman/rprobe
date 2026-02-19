"""
Channel Receiver 模块单元测试 - 简化版
"""

import socket
from unittest.mock import Mock

import pytest

from src.receivers import ChannelDataReceiver
from src.config.models import SSHConfig


class TestRecvOnce:
    """测试单次数据接收"""

    def test_recv_once_stdout_success(self):
        """测试成功接收 stdout 数据"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b"test data"

        data, truncated = receiver.recv_once(mock_channel, is_stderr=False, current_size=0)

        assert data == b"test data"
        assert truncated is False

    def test_recv_once_stderr_success(self):
        """测试成功接收 stderr 数据"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_stderr_ready.return_value = True
        mock_channel.recv_stderr.return_value = b"error message"

        data, truncated = receiver.recv_once(mock_channel, is_stderr=True, current_size=0)

        assert data == b"error message"
        assert truncated is False

    def test_recv_once_socket_error(self):
        """测试 socket 错误"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.side_effect = socket.error("Connection reset")

        with pytest.raises(ConnectionError) as exc_info:
            receiver.recv_once(mock_channel, is_stderr=False, current_size=0)

        assert "网络连接错误" in str(exc_info.value)


class TestRecvAll:
    """测试接收所有数据"""

    def test_recv_all_with_stdout_data(self):
        """测试带 stdout 数据的成功接收"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)

        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"Hello World"
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True

        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)

        assert exit_code == 0
        assert stdout == "Hello World"
        assert stderr == ""

    def test_recv_all_with_transport_disconnect(self):
        """测试传输层断开连接"""
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
