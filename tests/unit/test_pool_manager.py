"""
测试连接池管理器(PoolManager)的功能
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from rprobe.pooling import PoolManager, ConnectionPool
from rprobe.config.models import SSHConfig


class TestPoolManagerCreate:
    """测试连接池创建功能"""

    def test_create_pool_new(self):
        """测试创建新连接池"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
            port=22,
        )

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            pool = manager.create_pool(config, max_size=5, min_size=1, health_check_interval=0)

            assert pool is not None
            assert isinstance(pool, ConnectionPool)
            assert len(manager.list_pools()) == 1

    def test_create_pool_reuses_existing(self):
        """测试复用已存在的连接池"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
            port=22,
        )

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            pool1 = manager.create_pool(config, max_size=5, min_size=1, health_check_interval=0)
            pool2 = manager.create_pool(config, max_size=5, min_size=1, health_check_interval=0)

            # 验证是同一个对象
            assert pool1 is pool2
            assert len(manager.list_pools()) == 1

    def test_create_pool_resets_closed_pool(self):
        """测试创建时重置已关闭的连接池"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
            port=22,
        )

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            pool1 = manager.create_pool(config, max_size=5, min_size=2, health_check_interval=0)

            # 关闭连接池
            manager.close_pool(config)
            assert pool1._closed is True

            # 再次创建（应该复用并重置）
            pool2 = manager.create_pool(config, max_size=5, min_size=2, health_check_interval=0)

            # 验证是同一个对象但已重置
            assert pool1 is pool2
            assert pool1._closed is False

    def test_different_configs_different_pools(self):
        """测试不同配置创建不同连接池"""
        config1 = SSHConfig(
            host="host1.example.com",
            username="user1",
            password="pass1",
            port=22,
        )

        config2 = SSHConfig(
            host="host2.example.com",
            username="user2",
            password="pass2",
            port=22,
        )

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            pool1 = manager.create_pool(config1, max_size=3, min_size=1, health_check_interval=0)
            pool2 = manager.create_pool(config2, max_size=3, min_size=1, health_check_interval=0)

            assert pool1 is not pool2
            assert len(manager.list_pools()) == 2


class TestPoolManagerClose:
    """测试连接池关闭功能"""

    def test_close_pool_by_config(self):
        """测试通过配置关闭连接池"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
            port=22,
        )

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            pool = manager.create_pool(config, max_size=5, min_size=1, health_check_interval=0)

            # 关闭
            result = manager.close_pool(config)

            assert result is True
            assert pool._closed is True

    def test_close_nonexistent_pool(self):
        """测试关闭不存在的连接池"""
        config = SSHConfig(
            host="nonexistent.example.com",
            username="test",
            password="test",
            port=22,
        )

        manager = PoolManager()
        result = manager.close_pool(config)

        assert result is False

    def test_close_all_pools(self):
        """测试关闭所有连接池"""
        config1 = SSHConfig(host="host1.com", username="user1", password="pass1")
        config2 = SSHConfig(host="host2.com", username="user2", password="pass2")

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            pool1 = manager.create_pool(config1, max_size=3, min_size=1, health_check_interval=0)
            pool2 = manager.create_pool(config2, max_size=3, min_size=1, health_check_interval=0)

            # 关闭所有（保留在管理器中）
            manager.close_all()

            assert pool1._closed is True
            assert pool2._closed is True
            assert len(manager.list_pools()) == 2  # 仍然在列表中

    def test_close_all_and_remove(self):
        """测试关闭并移除所有连接池"""
        config1 = SSHConfig(host="host1.com", username="user1", password="pass1")
        config2 = SSHConfig(host="host2.com", username="user2", password="pass2")

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            manager.create_pool(config1, max_size=3, min_size=1, health_check_interval=0)
            manager.create_pool(config2, max_size=3, min_size=1, health_check_interval=0)

            # 关闭并从管理器中移除
            manager.close_all(remove_pools=True)

            assert len(manager.list_pools()) == 0


class TestPoolManagerGet:
    """测试获取连接池功能"""

    def test_get_pool_existing(self):
        """测试获取已存在的连接池"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
            port=22,
        )

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            pool1 = manager.create_pool(config, max_size=5, min_size=1, health_check_interval=0)

            pool2 = manager.get_pool(config)

            assert pool1 is pool2

    def test_get_pool_nonexistent(self):
        """测试获取不存在的连接池"""
        config = SSHConfig(
            host="nonexistent.example.com",
            username="test",
            password="test",
            port=22,
        )

        manager = PoolManager()
        pool = manager.get_pool(config)

        assert pool is None

    def test_get_or_create_pool(self):
        """测试获取或创建连接池"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
            port=22,
        )

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()

            # 第一次创建
            pool1 = manager.get_or_create_pool(
                config, max_size=5, min_size=1, health_check_interval=0
            )
            # 第二次获取
            pool2 = manager.get_or_create_pool(
                config, max_size=5, min_size=1, health_check_interval=0
            )

            assert pool1 is pool2


class TestPoolManagerRemove:
    """测试移除连接池功能"""

    def test_remove_pool(self):
        """测试移除连接池"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
            port=22,
        )

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            pool = manager.create_pool(config, max_size=5, min_size=1, health_check_interval=0)

            # 移除
            result = manager.remove_pool(config)

            assert result is True
            assert len(manager.list_pools()) == 0
            assert manager.get_pool(config) is None

    def test_remove_nonexistent_pool(self):
        """测试移除不存在的连接池"""
        config = SSHConfig(
            host="nonexistent.example.com",
            username="test",
            password="test",
            port=22,
        )

        manager = PoolManager()
        result = manager.remove_pool(config)

        assert result is False


class TestPoolManagerStats:
    """测试统计功能"""

    def test_get_all_stats(self):
        """测试获取所有连接池统计"""
        config1 = SSHConfig(host="host1.com", username="user1", password="pass1")
        config2 = SSHConfig(host="host2.com", username="user2", password="pass2")

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            manager.create_pool(config1, max_size=3, min_size=1, health_check_interval=0)
            manager.create_pool(config2, max_size=3, min_size=1, health_check_interval=0)

            stats = manager.get_all_stats()

            assert len(stats) == 2
            for pool_key, pool_stats in stats.items():
                assert "pool_size" in pool_stats or pool_stats.get("closed") is True

    def test_list_pools(self):
        """测试列出所有连接池"""
        config1 = SSHConfig(host="host1.com", username="user1", password="pass1")
        config2 = SSHConfig(host="host2.com", username="user2", password="pass2")

        with patch("rprobe.pooling.ConnectionManager") as mock_conn_class:
            mock_conn = Mock()
            mock_conn.is_connected = True
            mock_conn_class.return_value = mock_conn

            manager = PoolManager()
            manager.create_pool(config1, max_size=3, min_size=1, health_check_interval=0)
            manager.create_pool(config2, max_size=3, min_size=1, health_check_interval=0)

            pools = manager.list_pools()

            assert len(pools) == 2
            assert all("@" in pool_key for pool_key in pools)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
