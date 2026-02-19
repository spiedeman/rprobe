"""
测试并行创建连接池连接的功能
"""

import time
import pytest
from unittest.mock import Mock, patch

from src.pooling import ConnectionPool
from src.config.models import SSHConfig


class TestParallelConnectionCreation:
    """测试并行创建连接"""

    def test_parallel_creation_faster_than_serial(self):
        """测试并行创建比串行创建更快"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        call_count = [0]

        def mock_connect(*args, **kwargs):
            call_count[0] += 1
            time.sleep(0.01)  # 10ms延迟

        with patch("paramiko.SSHClient.connect", side_effect=mock_connect):
            # 串行创建
            call_count[0] = 0
            start = time.time()
            pool_serial = ConnectionPool(
                config, max_size=5, min_size=5, parallel_init=False, health_check_interval=0
            )
            serial_time = time.time() - start
            pool_serial.close()

            # 并行创建
            call_count[0] = 0
            start = time.time()
            pool_parallel = ConnectionPool(
                config, max_size=5, min_size=5, parallel_init=True, health_check_interval=0
            )
            parallel_time = time.time() - start
            pool_parallel.close()

        # 并行应该明显快于串行（至少2倍）
        speedup = serial_time / parallel_time
        print(
            f"\nSerial: {serial_time:.3f}s, Parallel: {parallel_time:.3f}s, Speedup: {speedup:.1f}x"
        )
        assert speedup >= 2.0, f"并行创建应该至少快2倍，实际只快了{speedup:.1f}倍"

    def test_parallel_creation_all_success(self):
        """测试并行创建所有连接都成功"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.backends.paramiko_backend.paramiko.SSHClient.connect"):
            pool = ConnectionPool(
                config, max_size=5, min_size=5, parallel_init=True, health_check_interval=0
            )

            # 验证创建了5个连接
            assert pool.stats["created"] == 5
            assert pool.stats["pool_size"] == 5

            pool.close()

    def test_parallel_creation_with_failures(self):
        """测试并行创建部分失败"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        call_count = [0]

        def mock_connect(*args, **kwargs):
            call_count[0] += 1
            # 第2和第4个连接失败
            if call_count[0] in [2, 4]:
                raise Exception("Connection failed")

        with patch("paramiko.SSHClient.connect", side_effect=mock_connect):
            pool = ConnectionPool(
                config, max_size=5, min_size=5, parallel_init=True, health_check_interval=0
            )

            # 验证部分连接创建成功
            assert pool.stats["created"] == 3  # 5 - 2 = 3
            assert pool.stats["pool_size"] == 3

            pool.close()

    def test_parallel_creation_single_connection(self):
        """测试并行创建单个连接（应该退化为串行）"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.backends.paramiko_backend.paramiko.SSHClient.connect"):
            pool = ConnectionPool(
                config, max_size=1, min_size=1, parallel_init=True, health_check_interval=0
            )

            # 单个连接应该也能正常工作
            assert pool.stats["created"] == 1

            pool.close()

    def test_parallel_creation_large_pool(self):
        """测试并行创建大量连接（限制并发数）"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.backends.paramiko_backend.paramiko.SSHClient.connect"):
            # 创建20个连接，但并发数应该被限制为10
            pool = ConnectionPool(
                config, max_size=20, min_size=20, parallel_init=True, health_check_interval=0
            )

            # 验证所有连接都创建成功
            assert pool.stats["created"] == 20

            pool.close()

    def test_parallel_vs_serial_same_result(self):
        """测试并行和串行创建结果一致"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.backends.paramiko_backend.paramiko.SSHClient.connect"):
            # 串行
            pool_serial = ConnectionPool(
                config, max_size=3, min_size=3, parallel_init=False, health_check_interval=0
            )
            serial_stats = pool_serial.stats.copy()
            pool_serial.close()

            # 并行
            pool_parallel = ConnectionPool(
                config, max_size=3, min_size=3, parallel_init=True, health_check_interval=0
            )
            parallel_stats = pool_parallel.stats.copy()
            pool_parallel.close()

        # 结果应该一致
        assert serial_stats["created"] == parallel_stats["created"]
        assert serial_stats["pool_size"] == parallel_stats["pool_size"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
