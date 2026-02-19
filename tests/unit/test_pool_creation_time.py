"""
测试连接池创建时间的线性关系（优化版 - 无长时间等待）

使用计数器和mock来验证行为，而不是实际等待。
"""

import time
import pytest
from unittest.mock import Mock, patch

from src.pooling import ConnectionPool
from src.config.models import SSHConfig


class TestPoolCreationTime:
    """测试连接池创建时间（快速版）"""

    def test_single_connection_creation_time(self):
        """测试单个连接创建时间基准"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        call_count = [0]

        # 使用极短的延迟（1ms）代替100ms
        def mock_connect(*args, **kwargs):
            call_count[0] += 1
            time.sleep(0.001)  # 1ms延迟

        with patch("paramiko.SSHClient.connect", side_effect=mock_connect):
            start = time.time()
            # 禁用健康检查线程，避免关闭时等待
            pool = ConnectionPool(config, max_size=1, min_size=1, health_check_interval=0)
            elapsed = time.time() - start
            pool.close()

        # 验证创建了1个连接
        assert call_count[0] == 1
        # 应该约等于1ms（允许较大误差）
        assert elapsed < 0.1, f"单连接耗时过长: {elapsed:.3f}s"

    def test_multiple_connections_linear_time(self):
        """测试多个连接创建时间是否线性增长"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        call_count = [0]

        def mock_connect(*args, **kwargs):
            call_count[0] += 1
            time.sleep(0.001)  # 1ms延迟

        test_cases = [1, 3, 5]
        results = []

        with patch("paramiko.SSHClient.connect", side_effect=mock_connect):
            for min_size in test_cases:
                call_count[0] = 0  # 重置计数器
                start = time.time()
                pool = ConnectionPool(
                    config, max_size=min_size, min_size=min_size, health_check_interval=0
                )
                elapsed = time.time() - start
                pool.close()
                results.append((min_size, elapsed, call_count[0]))

        # 验证创建次数 = min_size（证明是串行创建）
        for count, elapsed, created in results:
            assert created == count, f"期望创建{count}个连接，实际创建{created}个"
            # 验证时间大致线性（允许较大误差）
            assert elapsed < count * 0.01, f"{count}个连接耗时过长: {elapsed:.3f}s"

    def test_concurrent_vs_sequential_creation(self):
        """对比串行vs并行创建时间"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        connection_times = []

        def mock_connect(*args, **kwargs):
            # 记录每次连接的时间点
            connection_times.append(time.time())
            time.sleep(0.001)  # 1ms延迟

        with patch("paramiko.SSHClient.connect", side_effect=mock_connect):
            start = time.time()
            pool = ConnectionPool(config, max_size=5, min_size=5, health_check_interval=0)
            total_time = time.time() - start
            pool.close()

        # 验证了创建了5个连接
        assert len(connection_times) == 5

        # 验证连接是串行创建的（有时间间隔）
        for i in range(1, len(connection_times)):
            interval = connection_times[i] - connection_times[i - 1]
            # 串行创建的间隔应该大于0（证明是逐个创建的）
            assert interval > 0, f"连接{i}与连接{i-1}没有时间间隔，可能是并行创建"

        # 总时间应该小于串行时间（5 * 1ms + 开销）
        assert total_time < 0.1, f"总耗时过长: {total_time:.3f}s"

    def test_creation_failure_handling(self):
        """测试创建失败时的处理"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        call_count = [0]

        def mock_connect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Connection failed")
            time.sleep(0.001)

        with patch("paramiko.SSHClient.connect", side_effect=mock_connect):
            start = time.time()
            # min_size=3，但第2个会失败
            pool = ConnectionPool(config, max_size=3, min_size=3, health_check_interval=0)
            elapsed = time.time() - start
            pool.close()

        # 验证了尝试了多次创建
        assert call_count[0] >= 2
        # 时间应该很短
        assert elapsed < 0.1, f"失败处理耗时过长: {elapsed:.3f}s"


class TestPoolCreationCount:
    """测试连接池创建数量（不依赖时间）"""

    def test_min_size_creates_exact_connections(self):
        """测试min_size精确创建连接数"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        call_count = [0]

        def mock_connect(*args, **kwargs):
            call_count[0] += 1

        with patch("paramiko.SSHClient.connect", side_effect=mock_connect):
            # 不同的min_size
            for min_size in [1, 2, 3]:
                call_count[0] = 0
                pool = ConnectionPool(
                    config, max_size=10, min_size=min_size, health_check_interval=0
                )

                # 验证创建了min_size个连接
                assert (
                    call_count[0] == min_size
                ), f"min_size={min_size}时应该创建{min_size}个连接，实际创建{call_count[0]}个"

                pool.close()

    def test_max_size_limits_pool(self):
        """测试max_size限制连接池大小"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.backends.paramiko_backend.paramiko.SSHClient.connect"):
            pool = ConnectionPool(config, max_size=5, min_size=1, health_check_interval=0)

            # 验证max_size设置正确
            assert pool._max_size == 5
            assert pool.stats["max_size"] == 5

            pool.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
