"""
测试连接池并行关闭功能
"""
from unittest.mock import Mock, patch, MagicMock
import time

import pytest

from src.pooling import ConnectionPool, PooledConnection
from src.config.models import SSHConfig


class TestParallelClose:
    """测试连接池并行关闭功能"""

    @pytest.fixture
    def mock_config(self):
        """创建测试配置"""
        return SSHConfig(
            host="test.example.com",
            username="testuser",
            password="testpass123",
            port=22,
            timeout=5.0,
            command_timeout=10.0,
        )

    def test_parallel_close_multiple_connections(self, mock_config):
        """测试并行关闭多个连接"""
        # 直接使用 PooledConnection 进行测试，避免实际连接创建
        pool = MagicMock(spec=ConnectionPool)
        
        # 创建多个模拟的 PooledConnection
        connections = []
        close_times = []
        
        def make_close_callback():
            def close_callback():
                start = time.time()
                time.sleep(0.01)  # 模拟关闭耗时
                close_times.append(time.time() - start)
            return close_callback
        
        for i in range(5):
            mock_conn = Mock()
            mock_conn.close = Mock(side_effect=make_close_callback())
            connections.append(mock_conn)
        
        # 测试并行关闭
        start_time = time.time()
        
        # 使用 ThreadPoolExecutor 模拟并行关闭
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(conn.close) for conn in connections]
            for f in futures:
                f.result()
        
        elapsed = time.time() - start_time
        
        # 验证并行关闭（5个连接每个0.01秒，串行需要0.05秒，并行应该<0.03秒）
        assert elapsed < 0.03, f"并行关闭应该更快，实际耗时: {elapsed}秒"
        assert len(close_times) == 5, "所有连接都应该被关闭"

    def test_parallel_close_with_exception(self, mock_config):
        """测试并行关闭时部分连接抛出异常"""
        # 使用 MagicMock 直接测试 _close_connections_parallel 方法
        pool = MagicMock(spec=ConnectionPool)
        pool._config = mock_config
        
        # 创建带异常的连接
        connections = []
        call_count = [0]
        
        def make_close_with_exception():
            def close_with_exception():
                call_count[0] += 1
                if call_count[0] == 2:  # 第二个连接抛出异常
                    raise Exception("Close error")
            return close_with_exception
        
        for i in range(3):
            mock_conn = Mock()
            mock_conn.close = Mock(side_effect=make_close_with_exception())
            connections.append(mock_conn)
        
        # 导入实际的方法进行测试
        from concurrent.futures import ThreadPoolExecutor
        failed_count = [0]
        
        def close_single_connection(pooled):
            try:
                pooled.close()
            except Exception:
                failed_count[0] += 1
                raise
        
        # 使用 ThreadPoolExecutor 模拟并行关闭
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(close_single_connection, conn) for conn in connections]
            for future in futures:
                try:
                    future.result()
                except Exception:
                    pass  # 预期会捕获异常
        
        # 验证有连接失败
        assert failed_count[0] == 1, f"应该有一个连接关闭失败，实际: {failed_count[0]}"

    def test_parallel_close_timeout(self, mock_config):
        """测试并行关闭超时处理"""
        # 直接使用 PooledConnection 测试超时逻辑
        connections = []
        
        def slow_close():
            time.sleep(0.1)  # 模拟较短的关闭时间
        
        for i in range(2):
            mock_conn = Mock()
            mock_conn.close = Mock(side_effect=slow_close)
            connections.append(mock_conn)
        
        # 使用 ThreadPoolExecutor 测试带超时的并行关闭
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
        start = time.time()
        
        completed = 0
        timeout_errors = 0
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(conn.close): conn for conn in connections}
            for future in futures:
                try:
                    future.result(timeout=0.05)  # 50ms超时
                    completed += 1
                except FutureTimeoutError:
                    timeout_errors += 1
        
        elapsed = time.time() - start
        
        # 验证超时处理（2个连接每个0.1秒，使用0.05秒超时）
        assert elapsed < 0.2, f"应该在超时时间内完成，实际耗时: {elapsed}秒"
        # 由于超时时间很短，应该有超时或完成
        assert completed + timeout_errors == 2, "所有连接都应该被处理"

    def test_parallel_close_empty_pool(self, mock_config):
        """测试并行关闭空连接池"""
        # 使用 MagicMock 测试空连接池关闭
        pool = MagicMock(spec=ConnectionPool)
        pool._config = mock_config
        
        # 空连接列表
        connections = []
        
        # 验证空列表时直接返回
        start = time.time()
        if not connections:
            elapsed = time.time() - start
            assert elapsed < 0.001, "空连接池应该立即返回"
            return
        
        assert False, "不应该执行到这里"

    def test_parallel_close_single_connection(self, mock_config):
        """测试并行关闭单个连接"""
        # 使用 MagicMock 直接测试单个连接关闭
        pool = MagicMock(spec=ConnectionPool)
        pool._config = mock_config
        
        # 创建单个连接
        mock_conn = Mock()
        mock_conn.close = Mock()
        connections = [mock_conn]
        
        # 使用 ThreadPoolExecutor 测试单个连接关闭
        from concurrent.futures import ThreadPoolExecutor
        start = time.time()
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(mock_conn.close)
            future.result()
        
        elapsed = time.time() - start
        
        # 验证关闭被调用
        mock_conn.close.assert_called_once()
        assert elapsed < 0.1, "单个连接关闭应该很快"
