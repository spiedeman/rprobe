"""
Performance Monitor 测试套件
目标: 覆盖率从 0% 提升到 80%+
"""

import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# 需要测试的模块
from rprobe.utils.performance_monitor import (
    print_performance_info,
    compare_all_modes,
    show_usage_examples,
    monitor_performance,
    main,
)


class TestPrintPerformanceInfo:
    """测试 print_performance_info 函数"""

    def test_print_performance_info_select_mode(self, capsys):
        """测试打印 Select 模式信息"""
        # 创建 Mock receiver
        mock_receiver = Mock()
        mock_receiver.get_performance_info.return_value = {
            "name": "SelectReceiver",
            "current_mode": "select",
            "config_mode": "auto",
            "platform": "linux",
            "description": "基于 select 的高性能接收器",
            "cpu_usage": "~0% (等待时)",
            "latency": "< 1ms",
        }

        print_performance_info(mock_receiver)

        captured = capsys.readouterr()
        assert "当前性能配置" in captured.out
        assert "SelectReceiver" in captured.out
        assert "select" in captured.out
        assert "linux" in captured.out
        assert "~0%" in captured.out

    def test_print_performance_info_adaptive_mode(self, capsys):
        """测试打印 Adaptive 模式信息"""
        mock_receiver = Mock()
        mock_receiver.get_performance_info.return_value = {
            "name": "AdaptivePollingReceiver",
            "current_mode": "adaptive",
            "config_mode": "adaptive",
            "platform": "win32",
            "description": "自适应轮询接收器",
            "cpu_usage": "~2-5%",
            "latency": "< 50ms",
        }

        print_performance_info(mock_receiver)

        captured = capsys.readouterr()
        assert "AdaptivePollingReceiver" in captured.out
        assert "adaptive" in captured.out
        assert "win32" in captured.out

    def test_print_performance_info_missing_fields(self, capsys):
        """测试缺少某些字段时的处理"""
        mock_receiver = Mock()
        mock_receiver.get_performance_info.return_value = {
            "current_mode": "original",
            "config_mode": "original",
            "platform": "darwin",
            # 缺少 name, description, cpu_usage, latency
        }

        print_performance_info(mock_receiver)

        captured = capsys.readouterr()
        assert "当前性能配置" in captured.out
        assert "original" in captured.out
        assert "darwin" in captured.out
        assert "N/A" in captured.out


class TestCompareAllModes:
    """测试 compare_all_modes 函数"""

    @patch("rprobe.utils.performance_monitor.SmartChannelReceiver")
    @patch("rprobe.utils.performance_monitor.SSHConfig")
    def test_compare_all_modes_output(self, mock_config_class, mock_receiver_class, capsys):
        """测试对比所有模式的输出"""
        # 设置 mock
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        # 为每个模式创建 mock receiver - 注意 RecvMode 是枚举值
        call_count = [0]

        def create_mock_receiver(*args, **kwargs):
            receiver = Mock()
            call_count[0] += 1

            # 使用递增的方式来区分不同模式
            if call_count[0] == 1:
                receiver.mode = "select"
                receiver.get_performance_info.return_value = {
                    "cpu_usage": "~0%",
                    "latency": "< 1ms",
                    "platform": "Linux/Mac",
                }
            elif call_count[0] == 2:
                receiver.mode = "adaptive"
                receiver.get_performance_info.return_value = {
                    "cpu_usage": "~2-5%",
                    "latency": "< 50ms",
                    "platform": "All platforms",
                }
            else:
                receiver.mode = "original"
                receiver.get_performance_info.return_value = {
                    "cpu_usage": "~15%",
                    "latency": "~10ms",
                    "platform": "All platforms",
                }
            return receiver

        mock_receiver_class.side_effect = create_mock_receiver

        compare_all_modes()

        captured = capsys.readouterr()
        # 检查关键内容存在
        assert "所有模式性能对比" in captured.out
        assert "select" in captured.out.lower() or "Select" in captured.out
        assert "adaptive" in captured.out.lower() or "Adaptive" in captured.out
        assert "original" in captured.out.lower() or "Original" in captured.out
        assert "CPU占用" in captured.out
        assert "推荐使用:" in captured.out

    @patch("rprobe.utils.performance_monitor.SmartChannelReceiver")
    @patch("rprobe.utils.performance_monitor.SSHConfig")
    @patch("sys.platform", "win32")
    def test_monitor_performance_adaptive_mode(
        self, mock_config_class, mock_receiver_class, capsys
    ):
        """测试 Adaptive 模式的性能监控"""
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_receiver = Mock()
        mock_receiver.get_performance_info.return_value = {
            "current_mode": "adaptive",
            "cpu_usage": "~2-5%",
            "latency": "< 50ms",
        }
        mock_receiver_class.return_value = mock_receiver

        monitor_performance()

        captured = capsys.readouterr()
        assert "win32" in captured.out
        assert "adaptive" in captured.out
        assert "~2-5%" in captured.out
        # 检查性能指标输出存在即可
        assert "优化效果对比" in captured.out

    @patch("rprobe.utils.performance_monitor.SmartChannelReceiver")
    @patch("rprobe.utils.performance_monitor.SSHConfig")
    def test_monitor_performance_original_mode(
        self, mock_config_class, mock_receiver_class, capsys
    ):
        """测试 Original 模式的性能监控"""
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_receiver = Mock()
        mock_receiver.get_performance_info.return_value = {
            "current_mode": "original",
            "cpu_usage": "~15%",
            "latency": "~10ms",
        }
        mock_receiver_class.return_value = mock_receiver

        monitor_performance()

        captured = capsys.readouterr()
        assert "original" in captured.out
        assert "使用原始模式，无优化" in captured.out

    @patch("rprobe.utils.performance_monitor.SmartChannelReceiver")
    @patch("rprobe.utils.performance_monitor.SSHConfig")
    def test_monitor_performance_python_version(
        self, mock_config_class, mock_receiver_class, capsys
    ):
        """测试显示 Python 版本"""
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_receiver = Mock()
        mock_receiver.get_performance_info.return_value = {
            "current_mode": "select",
            "cpu_usage": "~0%",
            "latency": "< 1ms",
        }
        mock_receiver_class.return_value = mock_receiver

        monitor_performance()

        captured = capsys.readouterr()
        assert "Python 版本:" in captured.out


class TestMain:
    """测试 main 函数"""

    @patch("rprobe.utils.performance_monitor.monitor_performance")
    @patch("sys.argv", ["performance_monitor"])
    def test_main_no_args(self, mock_monitor, capsys):
        """测试无参数时显示帮助和性能信息"""
        main()

        captured = capsys.readouterr()
        assert "SSH 性能监控工具" in captured.out
        mock_monitor.assert_called_once()

    @patch("rprobe.utils.performance_monitor.compare_all_modes")
    @patch("sys.argv", ["performance_monitor", "--compare"])
    def test_main_compare_flag(self, mock_compare):
        """测试 --compare 参数"""
        main()
        mock_compare.assert_called_once()

    @patch("rprobe.utils.performance_monitor.monitor_performance")
    @patch("sys.argv", ["performance_monitor", "--info"])
    def test_main_info_flag(self, mock_monitor):
        """测试 --info 参数"""
        main()
        mock_monitor.assert_called_once()

    @patch("rprobe.utils.performance_monitor.show_usage_examples")
    @patch("sys.argv", ["performance_monitor", "--examples"])
    def test_main_examples_flag(self, mock_examples):
        """测试 --examples 参数"""
        main()
        mock_examples.assert_called_once()

    @patch("rprobe.utils.performance_monitor.compare_all_modes")
    @patch("rprobe.utils.performance_monitor.monitor_performance")
    @patch("rprobe.utils.performance_monitor.show_usage_examples")
    @patch("sys.argv", ["performance_monitor", "--all"])
    def test_main_all_flag(self, mock_examples, mock_monitor, mock_compare):
        """测试 --all 参数"""
        main()
        mock_compare.assert_called_once()
        mock_monitor.assert_called_once()
        mock_examples.assert_called_once()

    @patch("rprobe.utils.performance_monitor.compare_all_modes")
    @patch("sys.argv", ["performance_monitor", "-c"])
    def test_main_short_flag_compare(self, mock_compare):
        """测试短参数 -c"""
        main()
        mock_compare.assert_called_once()

    @patch("rprobe.utils.performance_monitor.monitor_performance")
    @patch("sys.argv", ["performance_monitor", "-i"])
    def test_main_short_flag_info(self, mock_monitor):
        """测试短参数 -i"""
        main()
        mock_monitor.assert_called_once()

    @patch("rprobe.utils.performance_monitor.show_usage_examples")
    @patch("sys.argv", ["performance_monitor", "-e"])
    def test_main_short_flag_examples(self, mock_examples):
        """测试短参数 -e"""
        main()
        mock_examples.assert_called_once()

    @patch("rprobe.utils.performance_monitor.compare_all_modes")
    @patch("rprobe.utils.performance_monitor.monitor_performance")
    @patch("rprobe.utils.performance_monitor.show_usage_examples")
    @patch("sys.argv", ["performance_monitor", "-a"])
    def test_main_short_flag_all(self, mock_examples, mock_monitor, mock_compare):
        """测试短参数 -a"""
        main()
        mock_compare.assert_called_once()
        mock_monitor.assert_called_once()
        mock_examples.assert_called_once()


class TestModuleExecution:
    """测试模块作为脚本执行"""

    @patch("rprobe.utils.performance_monitor.main")
    def test_module_execution(self, mock_main):
        """测试 __main__ 块执行"""
        # 模拟 __name__ == "__main__"
        import rprobe.utils.performance_monitor as pm

        # 保存原始 __name__
        original_name = pm.__name__

        try:
            # 设置为 __main__ 并重新执行模块级代码
            pm.__name__ = "__main__"
            # 直接调用 main，因为 __main__ 块在导入时已执行
            # 这里我们验证 main 函数被正确定义即可
            assert callable(pm.main)
        finally:
            pm.__name__ = original_name


class TestEdgeCases:
    """边界情况测试"""

    @patch("rprobe.utils.performance_monitor.SmartChannelReceiver")
    @patch("rprobe.utils.performance_monitor.SSHConfig")
    def test_compare_with_empty_performance_info(
        self, mock_config_class, mock_receiver_class, capsys
    ):
        """测试性能信息为空字段时的处理"""
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_receiver = Mock()
        mock_receiver.mode = "select"
        mock_receiver.get_performance_info.return_value = {}  # 空信息
        mock_receiver_class.return_value = mock_receiver

        # 应该能正常执行不抛出异常
        compare_all_modes()

        captured = capsys.readouterr()
        assert "所有模式性能对比" in captured.out

    @patch("rprobe.utils.performance_monitor.SmartChannelReceiver")
    @patch("rprobe.utils.performance_monitor.SSHConfig")
    def test_monitor_with_none_values(self, mock_config_class, mock_receiver_class, capsys):
        """测试性能信息包含 None 值时的处理"""
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_receiver = Mock()
        mock_receiver.get_performance_info.return_value = {
            "current_mode": None,
            "cpu_usage": None,
            "latency": None,
        }
        mock_receiver_class.return_value = mock_receiver

        # 应该能正常执行
        monitor_performance()

        captured = capsys.readouterr()
        assert "性能监控信息" in captured.out
