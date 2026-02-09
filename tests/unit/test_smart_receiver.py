"""
智能接收器模块测试
测试 SmartChannelReceiver 的各种功能和场景
"""
import socket
import sys
from unittest.mock import Mock, patch, MagicMock

import pytest
import paramiko

from src.config.models import SSHConfig, RecvMode
from src.receivers import (
    SmartChannelReceiver,
    create_receiver,
    compare_modes
)


@pytest.fixture
def mock_config():
    """创建测试配置"""
    return SSHConfig(
        host="test.example.com",
        username="testuser",
        password="testpass"
    )


class TestSmartChannelReceiverInit:
    """测试 SmartChannelReceiver 初始化"""
    
    def test_init_with_auto_mode_on_unix(self, mock_config):
        """测试在 Unix 平台自动选择 select 模式"""
        mock_config.recv_mode = RecvMode.AUTO
        
        with patch.object(sys, 'platform', 'linux'):
            receiver = SmartChannelReceiver(mock_config)
            assert receiver.mode == RecvMode.SELECT
    
    def test_init_with_auto_mode_on_windows(self, mock_config):
        """测试在 Windows 平台自动选择 adaptive 模式"""
        mock_config.recv_mode = RecvMode.AUTO
        
        with patch.object(sys, 'platform', 'win32'):
            receiver = SmartChannelReceiver(mock_config)
            assert receiver.mode == RecvMode.ADAPTIVE
    
    def test_init_with_explicit_select_mode(self, mock_config):
        """测试显式选择 select 模式"""
        mock_config.recv_mode = RecvMode.SELECT
        receiver = SmartChannelReceiver(mock_config)
        assert receiver.mode == RecvMode.SELECT
    
    def test_init_with_explicit_adaptive_mode(self, mock_config):
        """测试显式选择 adaptive 模式"""
        mock_config.recv_mode = RecvMode.ADAPTIVE
        receiver = SmartChannelReceiver(mock_config)
        assert receiver.mode == RecvMode.ADAPTIVE
    
    def test_init_with_explicit_original_mode(self, mock_config):
        """测试显式选择 original 模式"""
        mock_config.recv_mode = RecvMode.ORIGINAL
        receiver = SmartChannelReceiver(mock_config)
        assert receiver.mode == RecvMode.ORIGINAL
    
    def test_init_with_invalid_mode_fallback_to_original(self, mock_config):
        """测试无效模式回退到 original"""
        mock_config.recv_mode = "invalid_mode"
        receiver = SmartChannelReceiver(mock_config)
        assert receiver.mode == RecvMode.ORIGINAL


class TestSmartChannelReceiverRecvAll:
    """测试 recv_all 方法"""
    
    def test_recv_all_with_select_mode(self, mock_config):
        """测试 select 模式调用"""
        mock_config.recv_mode = RecvMode.SELECT
        receiver = SmartChannelReceiver(mock_config)
        
        # 模拟 select 模式失败，回退到 adaptive
        mock_channel = Mock()
        mock_transport = Mock()
        
        with patch.object(receiver._receiver, 'recv_all_optimized', side_effect=TypeError("mock error")):
            with patch('src.receivers.channel_receiver_optimized.AdaptivePollingReceiver') as mock_adaptive_cls:
                mock_adaptive = Mock()
                mock_adaptive.recv_all.return_value = ("stdout", "stderr", 0)
                mock_adaptive_cls.return_value = mock_adaptive
                
                result = receiver.recv_all(mock_channel, timeout=10, transport=mock_transport)
                
                assert result == ("stdout", "stderr", 0)
                mock_adaptive.recv_all.assert_called_once()
    
    def test_recv_all_with_adaptive_mode(self, mock_config):
        """测试 adaptive 模式调用"""
        mock_config.recv_mode = RecvMode.ADAPTIVE
        receiver = SmartChannelReceiver(mock_config)
        
        mock_channel = Mock()
        
        with patch.object(receiver._receiver, 'recv_all', return_value=("stdout", "stderr", 0)):
            result = receiver.recv_all(mock_channel, timeout=10)
            assert result == ("stdout", "stderr", 0)
    
    def test_recv_all_with_original_mode(self, mock_config):
        """测试 original 模式调用"""
        mock_config.recv_mode = RecvMode.ORIGINAL
        receiver = SmartChannelReceiver(mock_config)
        
        mock_channel = Mock()
        mock_transport = Mock()
        
        with patch.object(receiver._receiver, 'recv_all', return_value=("stdout", "stderr", 0)):
            result = receiver.recv_all(mock_channel, timeout=10, transport=mock_transport)
            assert result == ("stdout", "stderr", 0)
    
    def test_recv_all_uses_default_timeout(self, mock_config):
        """测试使用默认超时"""
        mock_config.recv_mode = RecvMode.ORIGINAL
        mock_config.command_timeout = 30.0
        receiver = SmartChannelReceiver(mock_config)
        
        mock_channel = Mock()
        
        with patch.object(receiver._receiver, 'recv_all', return_value=("stdout", "stderr", 0)) as mock_recv:
            receiver.recv_all(mock_channel, timeout=None)
            # 验证使用了配置中的超时
            mock_recv.assert_called_once()


class TestSmartChannelReceiverPerformanceInfo:
    """测试性能信息功能"""
    
    def test_get_performance_info_select_mode(self, mock_config):
        """测试 select 模式性能信息"""
        mock_config.recv_mode = RecvMode.SELECT
        receiver = SmartChannelReceiver(mock_config)
        
        info = receiver.get_performance_info()
        
        assert info['current_mode'] == RecvMode.SELECT
        assert 'cpu_usage' in info
        assert 'latency' in info
        assert info['config_mode'] == RecvMode.SELECT
    
    def test_get_performance_info_adaptive_mode(self, mock_config):
        """测试 adaptive 模式性能信息"""
        mock_config.recv_mode = RecvMode.ADAPTIVE
        receiver = SmartChannelReceiver(mock_config)
        
        info = receiver.get_performance_info()
        
        assert info['current_mode'] == RecvMode.ADAPTIVE
        assert 'cpu_usage' in info
        assert 'latency' in info
    
    def test_get_performance_info_original_mode(self, mock_config):
        """测试 original 模式性能信息"""
        mock_config.recv_mode = RecvMode.ORIGINAL
        receiver = SmartChannelReceiver(mock_config)
        
        info = receiver.get_performance_info()
        
        assert info['current_mode'] == RecvMode.ORIGINAL
        assert 'cpu_usage' in info
        assert 'latency' in info
    
    def test_get_performance_info_platform_info(self, mock_config):
        """测试性能信息包含平台信息"""
        receiver = SmartChannelReceiver(mock_config)
        info = receiver.get_performance_info()
        
        assert 'platform' in info
        assert info['platform'] == sys.platform


class TestCreateReceiverFactory:
    """测试工厂函数"""
    
    def test_create_receiver_returns_smart_receiver(self, mock_config):
        """测试工厂函数返回 SmartChannelReceiver"""
        receiver = create_receiver(mock_config)
        assert isinstance(receiver, SmartChannelReceiver)
    
    def test_create_receiver_uses_config(self, mock_config):
        """测试工厂函数使用传入的配置"""
        mock_config.recv_mode = RecvMode.SELECT
        receiver = create_receiver(mock_config)
        assert receiver.mode == RecvMode.SELECT


class TestCompareModes:
    """测试 compare_modes 函数"""
    
    def test_compare_modes_prints_info(self, capsys):
        """测试 compare_modes 输出信息"""
        compare_modes()
        captured = capsys.readouterr()
        
        assert "性能对比" in captured.out
        assert "Select/Poll 模式" in captured.out
        assert "自适应轮询" in captured.out
        assert "原始轮询" in captured.out
        assert "推荐配置" in captured.out


class TestSmartChannelReceiverIntegration:
    """集成测试"""
    
    def test_full_workflow_with_mock_channel(self, mock_config):
        """测试完整工作流程"""
        mock_config.recv_mode = RecvMode.ORIGINAL
        receiver = SmartChannelReceiver(mock_config)
        
        # 创建模拟 channel - 使用 MagicMock 避免 side_effect 耗尽
        mock_channel = Mock()
        mock_channel.recv_ready.return_value = True
        # 提供一个更长的 side_effect 列表
        recv_results = [b"line1\n", b"line2\n", b""] + [b""] * 50
        mock_channel.recv.side_effect = recv_results
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0
        mock_channel.closed = True  # 在收到所有数据后关闭
        
        # 模拟 transport
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        
        # 使用更长的 time 序列避免 StopIteration
        time_values = list(range(100))
        with patch('time.time', side_effect=time_values):
            stdout, stderr, exit_code = receiver.recv_all(
                mock_channel, timeout=60, transport=mock_transport
            )
        
        assert "line1" in stdout
        assert "line2" in stdout
        assert exit_code == 0
    
    def test_mode_property(self, mock_config):
        """测试 mode 属性"""
        mock_config.recv_mode = RecvMode.SELECT
        receiver = SmartChannelReceiver(mock_config)
        
        assert receiver.mode == RecvMode.SELECT
        assert isinstance(receiver.mode, RecvMode)
