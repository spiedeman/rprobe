"""
等待策略模块单元测试
测试自适应、阻塞式和混合等待策略
"""

import time
from unittest.mock import Mock, patch

import pytest

from src.utils.wait_strategies import (
    AdaptiveWaitStrategy,
    BlockingWaitStrategy,
    HybridWaitStrategy,
    calculate_average_wait,
)


class TestAdaptiveWaitStrategy:
    """测试自适应等待策略"""

    def test_initial_wait(self):
        """测试初始等待时间"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.01)
        assert waiter.current_wait == 0.01

    def test_wait_progression(self):
        """测试等待时间递增"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.01, growth_factor=2.0, max_wait=0.1)

        # 第一次等待后应该增长
        waiter.wait()
        assert waiter.current_wait == 0.02  # 0.01 * 2.0

        # 第二次等待
        waiter.wait()
        assert waiter.current_wait == 0.04  # 0.02 * 2.0

    def test_max_wait_limit(self):
        """测试最大等待时间限制"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.01, growth_factor=2.0, max_wait=0.03)

        # 等待多次直到达到上限
        waiter.wait()  # 0.01 -> 0.02
        waiter.wait()  # 0.02 -> 0.04，但上限是 0.03

        assert waiter.current_wait == 0.03

        # 继续等待不应该超过上限
        waiter.wait()
        assert waiter.current_wait == 0.03

    def test_reset(self):
        """测试重置功能"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.01)

        waiter.wait()
        assert waiter.current_wait > 0.01

        waiter.reset()
        assert waiter.current_wait == 0.01

    def test_wait_count(self):
        """测试等待计数"""
        waiter = AdaptiveWaitStrategy()

        assert waiter.wait_count == 0

        waiter.wait()
        assert waiter.wait_count == 1

        waiter.wait()
        assert waiter.wait_count == 2

        waiter.reset()
        # reset 不清除计数，只是重置等待时间
        assert waiter.wait_count == 2

    @patch("time.sleep")
    def test_actual_wait_time(self, mock_sleep):
        """测试实际等待时间"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.01)

        actual_wait = waiter.wait()

        mock_sleep.assert_called_once_with(0.01)
        assert actual_wait == 0.01

    def test_custom_parameters(self):
        """测试自定义参数"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.005, max_wait=0.05, growth_factor=1.5)

        assert waiter.initial_wait == 0.005

        waiter.wait()
        expected = 0.005 * 1.5
        assert waiter.current_wait == expected


class TestBlockingWaitStrategy:
    """测试阻塞式等待策略"""

    def test_init(self):
        """测试初始化"""
        strategy = BlockingWaitStrategy(timeout=5.0)
        assert strategy.timeout == 5.0

    def test_wait_for_data_success(self):
        """测试成功接收数据"""
        strategy = BlockingWaitStrategy(timeout=1.0)

        mock_recv = Mock(return_value=b"test data")

        result = strategy.wait_for_data(mock_recv)

        assert result == b"test data"
        mock_recv.assert_called_once_with(4096)

    def test_wait_for_data_empty(self):
        """测试接收空数据"""
        strategy = BlockingWaitStrategy(timeout=1.0)

        mock_recv = Mock(return_value=b"")

        result = strategy.wait_for_data(mock_recv)

        assert result == b""

    def test_wait_for_data_exception(self):
        """测试接收异常"""
        strategy = BlockingWaitStrategy(timeout=1.0)

        mock_recv = Mock(side_effect=Exception("Connection error"))

        result = strategy.wait_for_data(mock_recv)

        assert result is None

    def test_wait_for_data_custom_timeout(self):
        """测试自定义超时"""
        strategy = BlockingWaitStrategy(timeout=1.0)

        mock_recv = Mock(return_value=b"data")

        # 使用自定义超时覆盖默认值
        result = strategy.wait_for_data(mock_recv, timeout=0.5)

        assert result == b"data"


class TestHybridWaitStrategy:
    """测试混合等待策略"""

    def test_init(self):
        """测试初始化"""
        strategy = HybridWaitStrategy(
            poll_interval=0.01, blocking_threshold=5, blocking_timeout=0.1
        )

        assert strategy.poll_interval == 0.01
        assert strategy.blocking_threshold == 5
        assert strategy.blocking_timeout == 0.1

    @patch("time.sleep")
    def test_poll_phase(self, mock_sleep):
        """测试轮询阶段"""
        strategy = HybridWaitStrategy(poll_interval=0.01, blocking_threshold=3)

        # 模拟有数据的情况
        mock_has_data = Mock(return_value=True)

        result = strategy.wait(mock_has_data)

        assert result is True
        # 有数据时不应该 sleep
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_poll_phase_no_data(self, mock_sleep):
        """测试轮询阶段无数据"""
        strategy = HybridWaitStrategy(poll_interval=0.01, blocking_threshold=3)

        # 模拟无数据
        mock_has_data = Mock(return_value=False)

        result = strategy.wait(mock_has_data)

        # 应该进入轮询等待
        mock_sleep.assert_called_once_with(0.01)
        assert result is False

    @patch("time.sleep")
    def test_blocking_phase(self, mock_sleep):
        """测试阻塞阶段"""
        strategy = HybridWaitStrategy(
            poll_interval=0.01, blocking_threshold=2, blocking_timeout=0.5
        )

        # 第一次 wait：poll_count=1，小于阈值，使用 poll_interval
        mock_has_data1 = Mock(side_effect=[False, True])
        result1 = strategy.wait(mock_has_data1)
        assert result1 is True
        mock_sleep.assert_called_with(0.01)

        # 第二次 wait：poll_count=2，达到阈值，使用 blocking_timeout
        mock_sleep.reset_mock()
        mock_has_data2 = Mock(side_effect=[False, True])
        result2 = strategy.wait(mock_has_data2)
        assert result2 is True
        mock_sleep.assert_called_once_with(0.5)

    def test_reset(self):
        """测试重置计数"""
        strategy = HybridWaitStrategy(blocking_threshold=3)

        mock_has_data = Mock(return_value=False)

        # 进行几次轮询
        strategy.wait(mock_has_data)
        strategy.wait(mock_has_data)

        # 重置
        strategy.reset()

        # 再次检查内部状态
        mock_has_data_with_true = Mock(return_value=True)
        result = strategy.wait(mock_has_data_with_true)

        # 应该立即返回，不进入阻塞阶段
        assert result is True


class TestCalculateAverageWait:
    """测试平均等待时间计算"""

    def test_average_wait_calculation(self):
        """测试平均等待时间计算"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.01, growth_factor=2.0, max_wait=0.1)

        avg = calculate_average_wait(waiter, iterations=5)

        # 手动计算预期值
        # 0.01, 0.02, 0.04, 0.08, 0.1 (达到上限)
        expected_avg = (0.01 + 0.02 + 0.04 + 0.08 + 0.1) / 5
        assert avg == expected_avg

    def test_average_wait_with_early_limit(self):
        """测试早期达到上限的情况"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.05, growth_factor=2.0, max_wait=0.08)

        avg = calculate_average_wait(waiter, iterations=3)

        # 0.05, 0.08 (达到上限), 0.08
        expected_avg = (0.05 + 0.08 + 0.08) / 3
        assert avg == expected_avg

    def test_average_wait_single_iteration(self):
        """测试单次迭代"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.05)

        avg = calculate_average_wait(waiter, iterations=1)

        assert avg == 0.05

    def test_average_wait_no_growth(self):
        """测试无增长因子的情况"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.02, growth_factor=1.0, max_wait=1.0)  # 无增长

        avg = calculate_average_wait(waiter, iterations=10)

        # 所有等待时间都应该相同（允许浮点误差）
        assert abs(avg - 0.02) < 0.0001


class TestWaitStrategyIntegration:
    """集成测试：等待策略在实际场景中的应用"""

    def test_adaptive_wait_real_time(self):
        """测试自适应等待的实际时间"""
        waiter = AdaptiveWaitStrategy(
            initial_wait=0.001, max_wait=0.005, growth_factor=2.0  # 1ms  # 5ms
        )

        start = time.time()

        # 等待3次
        waiter.wait()
        waiter.wait()
        waiter.wait()

        elapsed = time.time() - start

        # 总等待时间应该在 7ms 左右 (1 + 2 + 4)
        assert 0.006 < elapsed < 0.01

    def test_hybrid_wait_scenario(self):
        """测试混合等待的实际场景"""
        strategy = HybridWaitStrategy(
            poll_interval=0.001, blocking_threshold=3, blocking_timeout=0.01
        )

        call_count = [0]

        def slow_data_check():
            call_count[0] += 1
            # wait() 先检查一次，然后 sleep 后再检查一次
            return call_count[0] >= 2

        start = time.time()
        result = strategy.wait(slow_data_check)
        elapsed = time.time() - start

        assert result is True
        # wait() 会调用 has_data 两次（sleep前和sleep后）
        assert call_count[0] == 2
        # 应该经历了轮询
        assert elapsed >= 0.001  # 至少有一些等待


class TestWaitStrategyEdgeCases:
    """边界情况测试"""

    def test_adaptive_zero_initial_wait(self):
        """测试初始等待为0的情况"""
        waiter = AdaptiveWaitStrategy(initial_wait=0)

        # 应该能正常工作，不会崩溃
        waiter.wait()
        assert waiter.current_wait == 0

    def test_adaptive_negative_growth(self):
        """测试异常增长因子"""
        # 增长因子小于1应该会导致等待时间减少
        waiter = AdaptiveWaitStrategy(initial_wait=0.1, growth_factor=0.5, max_wait=1.0)

        waiter.wait()
        # 等待时间应该减少
        assert waiter.current_wait == 0.05

    def test_adaptive_very_small_max(self):
        """测试最大等待小于初始值"""
        waiter = AdaptiveWaitStrategy(initial_wait=0.1, max_wait=0.05)

        # 首次等待后就应该达到上限
        waiter.wait()
        assert waiter.current_wait == 0.05

    def test_blocking_zero_timeout(self):
        """测试零超时"""
        strategy = BlockingWaitStrategy(timeout=0)

        mock_recv = Mock(return_value=b"data")
        result = strategy.wait_for_data(mock_recv)

        assert result == b"data"
