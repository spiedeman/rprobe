"""
Channel Receiver 覆盖率提升测试
针对未覆盖代码分支的补充测试
"""
import socket
import time
from unittest.mock import Mock, patch, call

import pytest

from src.receivers import ChannelDataReceiver
from src.config.models import SSHConfig


class TestChannelReceiverStderrScenarios:
    """测试 stderr 相关场景"""
    
    def test_stderr_truncation_warning(self, caplog):
        """测试 stderr 截断警告 (lines 139-141)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            max_output_size=10,
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        # 第一次返回 stdout 数据，第二次返回 stderr 数据（超过限制）
        mock_channel.recv_ready.side_effect = [True, False, False]
        mock_channel.recv.return_value = b"stdout"
        mock_channel.recv_stderr_ready.side_effect = [True, False]
        mock_channel.recv_stderr.return_value = b"stderr_data_that_exceeds"
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        with caplog.at_level("WARNING"):
            stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)
        
        assert exit_code == 0
        assert "错误输出超过最大限制" in caplog.text or "截断" in stderr
    
    def test_stderr_socket_timeout_continue(self, caplog):
        """测试 stderr socket 超时继续等待 (lines 142-143)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        # stdout 正常完成
        mock_channel.recv_ready.return_value = False
        # stderr 超时
        mock_channel.recv_stderr_ready.return_value = True
        mock_channel.recv_stderr.side_effect = socket.timeout("Timeout")
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        with caplog.at_level("DEBUG"):
            stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)
        
        assert exit_code == 0
        assert "接收 stderr 超时" in caplog.text
    
    def test_stderr_connection_error_propagates(self):
        """测试 stderr ConnectionError 传播 (lines 144-145)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = True
        mock_channel.recv_stderr.side_effect = ConnectionError("Network error")
        
        with pytest.raises(ConnectionError):
            receiver.recv_all(mock_channel, timeout=0.1)


class TestChannelReceiverCloseScenarios:
    """测试 channel 关闭场景"""
    
    def test_channel_close_with_stdout_residual(self):
        """测试 channel 关闭时读取 stdout 残留数据 (lines 161-166)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]  # 有残留数据
        mock_channel.recv.return_value = b"residual stdout data"
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)
        
        assert exit_code == 0
        assert "residual" in stdout
    
    def test_channel_close_with_stderr_residual(self):
        """测试 channel 关闭时读取 stderr 残留数据 (lines 169-176)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.side_effect = [True, False]  # 有残留数据
        mock_channel.recv_stderr.return_value = b"residual stderr data"
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)
        
        assert exit_code == 0
        assert "residual" in stderr
    
    def test_channel_close_with_both_residual(self):
        """测试 channel 关闭时同时有 stdout 和 stderr 残留数据"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        # 先 stdout，然后 stderr
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"stdout residual"
        mock_channel.recv_stderr_ready.side_effect = [True, False]
        mock_channel.recv_stderr.return_value = b"stderr residual"
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)
        
        assert exit_code == 0
        assert "stdout" in stdout
        assert "stderr" in stderr
    
    def test_channel_close_with_exit_code_not_ready(self):
        """测试 channel 关闭时 exit_status 未就绪 (line 179)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        # exit_status_ready 先 False 后 True
        mock_channel.exit_status_ready.side_effect = [False, True]
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)
        
        assert exit_code == 0
    
    def test_channel_close_get_exit_code(self):
        """测试 channel 关闭时获取 exit_code (lines 179-180)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        # exit_status_ready 先 False 后 True
        mock_channel.exit_status_ready.side_effect = [False, True]
        mock_channel.recv_exit_status.return_value = 42
        mock_channel.closed = True
        
        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)
        
        assert exit_code == 42


class TestChannelReceiverNoActivity:
    """测试长时间无数据活动场景 (lines 185-206)"""
    
    def test_no_activity_with_stdout_data(self):
        """测试长时间无活动但有 stdout 数据"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=5.0
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        # 模拟：有数据 -> 长时间无数据 -> 又有数据 -> 完成
        call_count = [0]
        def recv_ready_side_effect():
            call_count[0] += 1
            if call_count[0] <= 2:
                return True
            return False
        
        mock_channel.recv_ready.side_effect = recv_ready_side_effect
        mock_channel.recv.return_value = b"late data"
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = False
        
        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.5)
        
        assert exit_code == 0
        assert "late" in stdout
    
    def test_no_activity_with_stderr_data(self):
        """测试长时间无活动但有 stderr 数据"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=5.0
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        # 提供更多次的返回值
        mock_channel.recv_stderr_ready.side_effect = [True, True, False] + [False] * 100
        mock_channel.recv_stderr.return_value = b"late stderr"
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = False
        
        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.5)
        
        assert exit_code == 0
        assert "late" in stderr
    
    def test_no_activity_get_exit_code(self):
        """测试长时间无活动时获取 exit_code (lines 203-204)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=5.0
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        # exit_status_ready 在静默检测时返回 True
        mock_channel.exit_status_ready.side_effect = [False, True]
        mock_channel.recv_exit_status.return_value = 99
        mock_channel.closed = False
        
        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.5)
        
        assert exit_code == 99


class TestChannelReceiverTruncationMessages:
    """测试截断消息添加"""
    
    def test_stdout_truncation_message(self):
        """测试 stdout 截断消息添加 (line 221)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            max_output_size=5,
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"data that exceeds limit"
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)
        
        assert exit_code == 0
        assert "[输出已截断" in stdout
    
    def test_stderr_truncation_message(self):
        """测试 stderr 截断消息添加 (line 223)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            max_output_size=5,
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.side_effect = [True, False]
        mock_channel.recv_stderr.return_value = b"error that exceeds limit"
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        stdout, stderr, exit_code = receiver.recv_all(mock_channel, timeout=0.1)
        
        assert exit_code == 0
        assert "[错误输出已截断" in stderr


class TestChannelReceiverLogging:
    """测试日志记录"""
    
    def test_debug_logs(self, caplog):
        """测试调试日志记录 (line 180)"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        # 确保走 channel.closed 分支
        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        # exit_status_ready 先 False 让 exit_code 保持 -1，进入 closed 分支
        mock_channel.exit_status_ready.side_effect = [False, True]
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        with caplog.at_level("DEBUG"):
            receiver.recv_all(mock_channel, timeout=0.1)
        
        assert "Channel 被远程关闭" in caplog.text
    
    def test_data_received_logs(self, caplog):
        """测试数据接收日志"""
        config = SSHConfig(
            host="test.example.com",
            username="user",
            password="pass",
            command_timeout=0.1
        )
        receiver = ChannelDataReceiver(config)
        
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"test data"
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True
        
        with caplog.at_level("DEBUG"):
            receiver.recv_all(mock_channel, timeout=0.1)
        
        assert "接收到" in caplog.text
        assert "字节 stdout 数据" in caplog.text
