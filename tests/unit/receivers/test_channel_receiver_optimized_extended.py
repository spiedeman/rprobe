"""
Optimized Channel Receiver 扩展测试
补充测试以提高覆盖率: 54% -> 85%
"""
import socket
import time
from unittest.mock import Mock, MagicMock, patch

import pytest

from src.config.models import SSHConfig
from src.backends import ConnectionError

# 使用 TYPE_CHECKING 避免循环导入
from src.receivers.channel_receiver_optimized import (
    OptimizedChannelDataReceiver,
    AdaptivePollingReceiver,
    BatchedPromptDetector,
)


class TestOptimizedChannelDataReceiverExtended:
    """OptimizedChannelDataReceiver 扩展测试"""

    @pytest.fixture
    def config(self):
        return SSHConfig(
            host="test.com",
            username="user",
            password="pass",
            command_timeout=5.0,
            encoding="utf-8",
        )

    @pytest.fixture
    def receiver(self, config):
        return OptimizedChannelDataReceiver(config)

    def test_recv_all_with_channel_closed(self, receiver):
        """测试 channel 已关闭的情况"""
        channel = Mock()
        channel.closed = True
        channel.exit_status_ready = True
        channel.recv_exit_status.return_value = 0
        channel.setblocking = Mock()

        stdout, stderr, exit_code = receiver.recv_all_optimized(channel, timeout=5.0)

        assert exit_code == 0
        assert stdout == ""

    def test_recv_all_with_large_stderr(self, receiver):
        """测试大量 stderr 数据"""
        channel = Mock()
        channel.closed = False
        channel.exit_status_ready = True
        channel.recv_exit_status.return_value = 1
        channel.setblocking = Mock()

        # 模拟大量 stderr
        stderr_data = b"Error " * 1000
        channel.recv.return_value = b""
        channel.recv_stderr.return_value = stderr_data

        with patch("select.select", return_value=([channel], [], [])):
            stdout, stderr, exit_code = receiver.recv_all_optimized(
                channel, timeout=5.0
            )

        assert exit_code == 1
        assert len(stderr) > 0

    def test_recv_all_truncation_stderr(self, receiver):
        """测试 stderr 截断"""
        receiver._config.max_output_size = 100

        channel = Mock()
        channel.closed = False
        channel.exit_status_ready = True
        channel.recv_exit_status.return_value = 0
        channel.setblocking = Mock()

        # 超过限制的 stderr
        channel.recv.return_value = b""
        channel.recv_stderr.return_value = b"E" * 200

        with patch("select.select", return_value=([channel], [], [])):
            stdout, stderr, exit_code = receiver.recv_all_optimized(
                channel, timeout=5.0
            )

        assert "截断" in stderr

    def test_recv_all_with_socket_error_on_recv(self, receiver):
        """测试 recv 时 socket 错误"""
        channel = Mock()
        channel.closed = False
        channel.exit_status_ready = True
        channel.recv_exit_status.return_value = 0
        channel.setblocking = Mock()

        # recv 抛出 socket 错误
        channel.recv.side_effect = socket.error("Socket error")
        channel.recv_stderr.return_value = b""

        with patch("select.select", return_value=([channel], [], [])):
            # 应该处理错误并继续
            stdout, stderr, exit_code = receiver.recv_all_optimized(
                channel, timeout=5.0
            )

        assert exit_code == 0


class TestAdaptivePollingReceiverExtended:
    """AdaptivePollingReceiver 扩展测试"""

    @pytest.fixture
    def config(self):
        return SSHConfig(
            host="test.com",
            username="user",
            password="pass",
            command_timeout=5.0,
            max_output_size=1024 * 1024,
            encoding="utf-8",
        )

    @pytest.fixture
    def receiver(self, config):
        return AdaptivePollingReceiver(config)

    def test_recv_all_with_channel_closed_immediately(self, receiver):
        """测试 channel 立即关闭"""
        channel = Mock()
        channel.closed = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = True
        channel.recv_exit_status.return_value = 0

        stdout, stderr, exit_code = receiver.recv_all(channel, timeout=5.0)

        assert exit_code == 0

    def test_recv_all_with_multiple_data_chunks(self, receiver):
        """测试多个数据块"""
        channel = Mock()
        channel.closed = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False

        # 模拟多次数据接收
        data_chunks = [b"Chunk1", b"Chunk2", b"Chunk3"]
        chunk_index = [0]

        def recv_side_effect(*args):
            if chunk_index[0] < len(data_chunks):
                data = data_chunks[chunk_index[0]]
                chunk_index[0] += 1
                return data
            return b""

        def recv_ready_side_effect():
            return chunk_index[0] < len(data_chunks)

        channel.recv.side_effect = recv_side_effect
        channel.recv_ready.side_effect = recv_ready_side_effect

        # 第三次调用后退出
        call_count = [0]

        def exit_status_side_effect():
            call_count[0] += 1
            return call_count[0] >= 5

        channel.exit_status_ready.side_effect = exit_status_side_effect
        channel.recv_exit_status.return_value = 0

        stdout, stderr, exit_code = receiver.recv_all(channel, timeout=5.0)

        assert exit_code == 0
        assert "Chunk1" in stdout
        assert "Chunk2" in stdout
        assert "Chunk3" in stdout

    def test_recv_all_with_stderr_only(self, receiver):
        """测试只有 stderr"""
        channel = Mock()
        channel.closed = False
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = True
        channel.recv_stderr.return_value = b"Error message"
        channel.exit_status_ready = True
        channel.recv_exit_status.return_value = 1

        stdout, stderr, exit_code = receiver.recv_all(channel, timeout=5.0)

        assert exit_code == 1
        assert "Error message" in stderr
        assert stdout == ""

    def test_recv_stream_with_large_data(self, receiver):
        """测试流式接收大数据"""
        chunks = []

        def handler(stdout, stderr):
            if stdout:
                chunks.append(stdout)

        channel = Mock()
        channel.closed = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False

        # 模拟大数据流
        data_size = [0]

        def recv_side_effect(*args):
            if data_size[0] < 100000:  # 100KB
                data = b"X" * 10000
                data_size[0] += len(data)
                return data
            return b""

        def recv_ready_side_effect():
            return data_size[0] < 100000

        channel.recv.side_effect = recv_side_effect
        channel.recv_ready.side_effect = recv_ready_side_effect

        # 延迟退出
        call_count = [0]

        def exit_status_side_effect():
            call_count[0] += 1
            return data_size[0] >= 100000 and call_count[0] > 10

        channel.exit_status_ready.side_effect = exit_status_side_effect
        channel.recv_exit_status.return_value = 0

        exit_code = receiver.recv_stream(channel, handler, timeout=10.0)

        assert exit_code == 0
        assert sum(len(c) for c in chunks) >= 100000


class TestBatchedPromptDetectorExtended:
    """BatchedPromptDetector 扩展测试"""

    @pytest.fixture
    def mock_detector(self):
        detector = Mock()
        detector.is_prompt_line.return_value = True
        return detector

    def test_should_check_time_only(self, mock_detector):
        """测试仅时间条件满足"""
        from src.receivers.channel_receiver_optimized import BatchedPromptDetector

        detector = BatchedPromptDetector(
            mock_detector, check_interval=0.1, min_data_size=100
        )

        # 立即检查 - 应该可以
        assert detector.should_check(200) is True

        # 记录检查时间
        detector._last_check_time = time.time()

        # 短时间内再次检查 - 不应该
        assert detector.should_check(300) is False

    def test_should_check_size_only(self, mock_detector):
        """测试仅数据量条件满足"""
        from src.receivers.channel_receiver_optimized import BatchedPromptDetector

        detector = BatchedPromptDetector(
            mock_detector, check_interval=0.1, min_data_size=100
        )

        # 时间满足但数据量不满足
        detector._last_check_time = time.time() - 0.2

        assert detector.should_check(50) is False
        assert detector.should_check(200) is True

    def test_check_updates_both_tracking_vars(self, mock_detector):
        """测试检查更新所有跟踪变量"""
        from src.receivers.channel_receiver_optimized import BatchedPromptDetector

        detector = BatchedPromptDetector(
            mock_detector, check_interval=0.1, min_data_size=10
        )

        old_time = detector._last_check_time
        old_size = detector._last_check_size

        result = detector.check("some output data here")

        assert result is True
        assert detector._last_check_time > old_time
        assert detector._last_check_size > old_size
        assert detector._last_check_size == len("some output data here")


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_config_encoding(self):
        """测试配置编码"""
        config = SSHConfig(
            host="test.com", username="user", password="pass", encoding="latin-1"
        )
        receiver = AdaptivePollingReceiver(config)

        assert receiver._config.encoding == "latin-1"

    def test_unicode_handling(self):
        """测试 Unicode 处理"""
        config = SSHConfig(host="test.com", username="user", password="pass")
        receiver = AdaptivePollingReceiver(config)

        channel = Mock()
        channel.closed = False
        channel.recv_ready.return_value = True
        channel.recv.return_value = "你好世界".encode("utf-8")
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = True
        channel.recv_exit_status.return_value = 0

        stdout, stderr, exit_code = receiver.recv_all(channel, timeout=5.0)

        assert "你好世界" in stdout
        assert exit_code == 0

    def test_binary_data_with_replace(self):
        """测试二进制数据替换"""
        config = SSHConfig(host="test.com", username="user", password="pass")
        receiver = AdaptivePollingReceiver(config)

        channel = Mock()
        channel.closed = False
        channel.recv_ready.return_value = True
        # 包含无效 UTF-8 序列
        channel.recv.return_value = b"\xff\xfe\x00\x01"
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = True
        channel.recv_exit_status.return_value = 0

        # 不应该抛出异常
        stdout, stderr, exit_code = receiver.recv_all(channel, timeout=5.0)

        assert exit_code == 0
        assert isinstance(stdout, str)
