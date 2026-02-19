"""
测试连接池的连接管理功能
（关闭特定连接、批量关闭、关闭空闲连接等）
"""

import time
import pytest
from unittest.mock import Mock, patch

from src.pooling import ConnectionPool
from src.config.models import SSHConfig


class TestConnectionPoolGetConnectionsInfo:
    """测试获取连接信息功能"""

    def test_get_connections_info_empty_pool(self):
        """测试空连接池的信息"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=0, health_check_interval=0)

            info = pool.get_connections_info()

            assert isinstance(info, list)
            assert len(info) == 0

    def test_get_connections_info_with_idle(self):
        """测试获取空闲连接信息"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

            info = pool.get_connections_info()

            assert len(info) == 2
            for conn_info in info:
                assert "id" in conn_info
                assert "status" in conn_info
                assert conn_info["status"] == "idle"
                assert "created_at" in conn_info
                assert "use_count" in conn_info
                assert "is_healthy" in conn_info

    def test_get_connections_info_with_in_use(self):
        """测试获取使用中连接信息"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

            # 获取一个连接使用
            with pool.get_connection() as conn:
                info = pool.get_connections_info()

                # 应该有1个空闲，1个使用中
                idle_count = sum(1 for c in info if c["status"] == "idle")
                in_use_count = sum(1 for c in info if c["status"] == "in_use")

                assert idle_count == 1
                assert in_use_count == 1


class TestConnectionPoolCloseConnectionById:
    """测试关闭指定ID连接"""

    def test_close_connection_by_id_success(self):
        """测试成功关闭指定连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

            # 获取第一个连接的ID
            info = pool.get_connections_info()
            first_id = info[0]["id"]

            # 关闭该连接
            result = pool.close_connection_by_id(first_id)

            assert result is True
            assert pool.stats["pool_size"] == 1

    def test_close_connection_by_id_not_found(self):
        """测试关闭不存在的连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

            # 尝试关闭不存在的ID
            result = pool.close_connection_by_id("nonexistent_id")

            assert result is False

    def test_close_connection_by_id_in_use(self):
        """测试无法关闭使用中的连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

            # 获取一个连接使用
            with pool.get_connection() as conn:
                # 获取使用中连接的ID
                info = pool.get_connections_info()
                in_use_conn = [c for c in info if c["status"] == "in_use"][0]

                # 尝试关闭使用中的连接
                result = pool.close_connection_by_id(in_use_conn["id"])

                assert result is False


class TestConnectionPoolCloseConnections:
    """测试批量关闭连接"""

    def test_close_connections_oldest_strategy(self):
        """测试关闭最老的连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=3, health_check_interval=0)

            # 关闭最老的1个连接
            closed = pool.close_connections(1, strategy="oldest")

            assert closed == 1
            assert pool.stats["pool_size"] == 2

    def test_close_connections_newest_strategy(self):
        """测试关闭最新的连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=3, health_check_interval=0)

            # 关闭最新的1个连接
            closed = pool.close_connections(1, strategy="newest")

            assert closed == 1
            assert pool.stats["pool_size"] == 2

    def test_close_connections_least_used_strategy(self):
        """测试关闭使用最少的连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=3, health_check_interval=0)

            # 使用一些连接
            with pool.get_connection() as conn:
                pass

            # 关闭使用最少的1个连接
            closed = pool.close_connections(1, strategy="least_used")

            assert closed == 1
            assert pool.stats["pool_size"] == 2

    def test_close_connections_exceed_available(self):
        """测试关闭数量超过可用连接数"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

            # 尝试关闭10个连接（但只有2个可用）
            closed = pool.close_connections(10, strategy="oldest")

            assert closed == 2
            assert pool.stats["pool_size"] == 0

    def test_close_connections_zero_count(self):
        """测试关闭0个连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

            closed = pool.close_connections(0)

            assert closed == 0
            assert pool.stats["pool_size"] == 2


class TestConnectionPoolCloseIdleConnections:
    """测试关闭空闲连接"""

    def test_close_idle_connections_success(self):
        """测试成功关闭空闲连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

            # 等待一下使连接变为空闲
            time.sleep(0.1)

            # 关闭空闲超过50ms的连接
            closed = pool.close_idle_connections(min_idle_time=0.05)

            assert closed == 2
            assert pool.stats["pool_size"] == 0

    def test_close_idle_connections_none_idle(self):
        """测试没有空闲连接时"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

            # 立即关闭（连接尚未空闲足够时间）
            closed = pool.close_idle_connections(min_idle_time=10)

            assert closed == 0


class TestConnectionPoolCloseByFilter:
    """测试根据条件关闭连接"""

    def test_close_connections_by_filter(self):
        """测试根据自定义条件关闭连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=3, health_check_interval=0)

            # 关闭使用次数为0的连接
            closed = pool.close_connections_by_filter(lambda c: c.use_count == 0)

            assert closed == 3
            assert pool.stats["pool_size"] == 0

    def test_close_connections_by_filter_no_match(self):
        """测试没有匹配条件的连接"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

            # 使用一个连接
            with pool.get_connection() as conn:
                pass

            # 尝试关闭使用次数为100的连接（不存在）
            closed = pool.close_connections_by_filter(lambda c: c.use_count == 100)

            assert closed == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
