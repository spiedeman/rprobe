"""
测试连接池的关闭和重置功能
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from src.pooling import ConnectionPool
from src.config.models import SSHConfig


class TestConnectionPoolClose:
    """测试连接池关闭功能"""

    def test_close_keeps_object_alive(self):
        """测试关闭后对象仍然存活"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=2, min_size=2, health_check_interval=0)

            # 关闭连接池
            pool.close()

            # 验证对象仍然存在
            assert pool is not None
            assert pool._closed is True
            assert pool.stats["pool_size"] == 0

    def test_close_prevents_new_acquisitions(self):
        """测试关闭后无法获取新连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=2, min_size=1, health_check_interval=0)
            pool.close()

            # 验证无法获取连接
            with pytest.raises(RuntimeError) as exc_info:
                with pool.get_connection() as conn:
                    pass

            assert "closed" in str(exc_info.value).lower()

    def test_close_all_connections(self):
        """测试关闭所有连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        mock_connections = []

        def create_mock_conn(*args, **kwargs):
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_connections.append(mock_conn)
            return mock_conn

        with patch("src.pooling.ConnectionManager", side_effect=create_mock_conn):
            pool = ConnectionPool(config, max_size=3, min_size=3, health_check_interval=0)

            # 获取一个连接使用
            with pool.get_connection() as conn:
                pass

            # 关闭连接池
            pool.close()

            # 验证所有连接都被关闭
            for mock_conn in mock_connections:
                mock_conn.disconnect.assert_called()


class TestConnectionPoolReset:
    """测试连接池重置功能"""

    def test_reset_after_close(self):
        """测试关闭后重置"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=2, min_size=2, health_check_interval=0)
            initial_id = id(pool)

            # 关闭
            pool.close()
            assert pool._closed is True

            # 重置
            pool.reset()

            # 验证对象ID不变
            assert id(pool) == initial_id
            assert pool._closed is False
            assert pool.stats["pool_size"] == 2

    def test_reset_without_close(self):
        """测试直接重置（无需先关闭）"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=2, min_size=2, health_check_interval=0)

            # 直接重置
            pool.reset()

            # 验证仍然可用
            assert pool._closed is False
            assert pool.stats["pool_size"] == 2

    def test_reset_clears_stats(self):
        """测试重置清除统计信息"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=2, min_size=2, health_check_interval=0)

            # 记录一些统计
            with pool.get_connection() as conn:
                pass

            initial_created = pool.stats["created"]
            assert initial_created > 0

            # 重置
            pool.reset()

            # 验证统计被重置
            assert pool.stats["created"] == 2  # min_size个新连接

    def test_reset_reinitializes_connections(self):
        """测试重置重新初始化连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        create_count = [0]

        def create_mock_conn(*args, **kwargs):
            mock_conn = Mock()
            mock_conn.is_connected = True
            create_count[0] += 1
            return mock_conn

        with patch("src.pooling.ConnectionManager", side_effect=create_mock_conn):
            pool = ConnectionPool(config, max_size=2, min_size=2, health_check_interval=0)

            # 记录初始创建数
            initial_count = create_count[0]

            # 重置
            pool.reset()

            # 验证创建了新的连接
            assert create_count[0] > initial_count

    def test_pool_usable_after_reset(self):
        """测试重置后连接池可正常使用"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=2, min_size=2, health_check_interval=0)

            # 关闭并重置
            pool.close()
            pool.reset()

            # 验证可以正常使用
            with pool.get_connection() as conn:
                assert conn is not None

            # 验证统计正确
            stats = pool.stats
            assert stats["pool_size"] >= 1


class TestConnectionPoolContextManager:
    """测试连接池上下文管理器"""

    def test_context_manager_closes_pool(self):
        """测试上下文管理器自动关闭连接池"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            with ConnectionPool(config, max_size=1, min_size=1, health_check_interval=0) as pool:
                assert pool._closed is False

            # 退出上下文后应该已关闭
            assert pool._closed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
