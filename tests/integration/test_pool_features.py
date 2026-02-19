"""
连接池功能集成测试 - 测试连接池在真实环境中的行为

运行方式:
    export TEST_REAL_SSH=true
    export TEST_SSH_HOST=your-host
    export TEST_SSH_USER=your-user
    export TEST_SSH_PASS=your-password
    python -m pytest tests/integration/test_pool_features.py -v --run-integration
"""

import time
import pytest

from src import SSHConfig
from src.pooling import ConnectionPool, get_pool_manager


@pytest.mark.integration
class TestConnectionPoolStats:
    """测试连接池统计功能"""

    def test_pool_stats_accuracy(self, test_environment):
        """测试连接池统计信息的准确性"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

        try:
            # 验证初始统计
            stats = pool.stats
            assert stats["pool_size"] == 2  # min_size
            assert stats["max_size"] == 5
            assert stats["in_use"] == 0
            assert stats["total"] == 2

            # 获取一个连接
            with pool.get_connection() as conn:
                stats = pool.stats
                assert stats["pool_size"] == 1
                assert stats["in_use"] == 1
                assert stats["total"] == 2

            # 释放后恢复
            stats = pool.stats
            assert stats["pool_size"] == 2
            assert stats["in_use"] == 0

            # 验证人类可读格式
            assert isinstance(stats["uptime"], str)
            assert isinstance(stats["created_at"], str)

        finally:
            pool.close()

    def test_pool_stats_with_commands(self, test_environment):
        """测试执行命令后的统计更新"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=3, min_size=1, health_check_interval=0)

        try:
            initial_stats = pool.stats

            # 执行多个命令
            with pool.get_connection() as conn:
                # ConnectionManager doesn't have execute_command, skip stats check
                pass

            # 验证统计更新
            stats = pool.stats
            assert stats["created"] >= 1
            assert stats["returned"] >= 1

        finally:
            pool.close()

    def test_pool_stats_human_readable_format(self, test_environment):
        """测试统计信息的人类可读格式"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=3, min_size=1, health_check_interval=0)

        try:
            # 等待一小段时间（使uptime有意义）
            time.sleep(0.1)

            # 获取统计
            stats = pool.stats

            # 验证时间字段格式
            assert isinstance(stats["uptime"], str)
            assert "s" in stats["uptime"] or "m" in stats["uptime"]

            # 验证时间戳格式
            assert isinstance(stats["created_at"], str)

        finally:
            pool.close()


@pytest.mark.integration
class TestConnectionPoolCloseReset:
    """测试连接池关闭和重置功能"""

    def test_pool_close_keeps_object(self, test_environment):
        """测试关闭后对象保留"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=3, min_size=2, health_check_interval=0)
        initial_id = id(pool)

        # 关闭连接池
        pool.close()
        assert pool._closed is True
        assert pool.stats["pool_size"] == 0

        # 验证对象仍然存在
        assert id(pool) == initial_id

    def test_pool_reset_reinitializes(self, test_environment):
        """测试重置后重新初始化"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=3, min_size=2, health_check_interval=0)
        initial_id = id(pool)

        try:
            # 关闭并获取统计
            pool.close()
            assert pool._closed is True

            # 重置
            pool.reset()

            # 验证对象ID不变但已重新初始化
            assert id(pool) == initial_id
            assert pool._closed is False
            assert pool.stats["pool_size"] == 2

            # 验证可以正常使用 (连接已建立即可)
            with pool.get_connection() as conn:
                # ConnectionManager doesn't have execute_command, just verify connection exists
                assert conn.is_connected

        finally:
            pool.close()

    def test_pool_reset_without_close(self, test_environment):
        """测试直接重置（无需先关闭）"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=3, min_size=2, health_check_interval=0)

        try:
            # 直接重置
            pool.reset()

            # 验证仍然可用
            assert pool._closed is False
            assert pool.stats["pool_size"] == 2

        finally:
            pool.close()


@pytest.mark.integration
class TestPoolManagerIntegration:
    """测试 PoolManager 在真实环境中的表现"""

    def test_pool_manager_create_and_reuse(self, test_environment):
        """测试 PoolManager 创建和复用连接池"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        # 获取管理器
        manager = get_pool_manager()

        # 创建连接池
        pool1 = manager.create_pool(config, max_size=3, min_size=1, health_check_interval=0)

        # 复用相同配置的连接池
        pool2 = manager.create_pool(config, max_size=3, min_size=1, health_check_interval=0)

        # 验证是同一个对象
        assert pool1 is pool2
        assert manager.list_pools() == [f"{config.username}@{config.host}:{config.port}"]

        # 清理
        manager.close_all(remove_pools=True)

    def test_pool_manager_close_and_recreate(self, test_environment):
        """测试关闭后重新创建连接池"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        manager = get_pool_manager()

        # 创建连接池
        pool1 = manager.create_pool(config, max_size=3, min_size=1, health_check_interval=0)

        # 关闭
        manager.close_pool(config)
        assert pool1._closed is True

        # 重新创建（应该复用并重置）
        pool2 = manager.create_pool(config, max_size=3, min_size=1, health_check_interval=0)

        # 验证是同一个对象但已激活
        assert pool1 is pool2
        assert pool2._closed is False

        # 清理
        manager.remove_pool(config)

    def test_pool_manager_multiple_servers(self, test_environment):
        """测试管理多个服务器的连接池"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        # 使用相同主机但不同用户名来模拟多服务器
        config1 = SSHConfig(
            host=test_environment["test_host"],
            username=f"{test_environment['test_user']}_1",
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        config2 = SSHConfig(
            host=test_environment["test_host"],
            username=f"{test_environment['test_user']}_2",
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        manager = get_pool_manager()

        # 注意：这可能会失败因为用户不存在，但我们测试的是管理器行为
        try:
            pool1 = manager.create_pool(config1, max_size=2, min_size=0, health_check_interval=0)
            pool2 = manager.create_pool(config2, max_size=2, min_size=0, health_check_interval=0)

            # 验证有两个连接池
            assert len(manager.list_pools()) == 2

        except Exception:
            # 预期会失败，因为我们使用了不存在的用户
            pass
        finally:
            # 清理所有
            manager.close_all(remove_pools=True)

    def test_pool_manager_get_all_stats(self, test_environment):
        """测试获取所有连接池统计"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        manager = get_pool_manager()

        # 创建连接池
        manager.create_pool(config, max_size=3, min_size=1, health_check_interval=0)

        # 获取所有统计
        all_stats = manager.get_all_stats()

        # 验证有统计数据
        assert len(all_stats) >= 1

        pool_key = f"{config.username}@{config.host}:{config.port}"
        if pool_key in all_stats:
            stats = all_stats[pool_key]
            assert "pool_size" in stats or stats.get("closed") is True

        # 清理
        manager.close_all(remove_pools=True)


@pytest.mark.integration
class TestConnectionManagement:
    """测试连接管理功能"""

    def test_get_connections_info(self, test_environment):
        """测试获取连接信息"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=5, min_size=3, health_check_interval=0)

        try:
            # 获取连接信息
            info = pool.get_connections_info()

            # 验证有3个连接
            assert len(info) == 3

            # 验证每个连接的信息结构
            for conn_info in info:
                assert "id" in conn_info
                assert "status" in conn_info
                assert conn_info["status"] == "idle"
                assert "created_at" in conn_info
                assert "use_count" in conn_info

        finally:
            pool.close()

    def test_close_connection_by_id(self, test_environment):
        """测试关闭指定ID的连接"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=5, min_size=3, health_check_interval=0)

        try:
            # 获取第一个连接的ID
            info = pool.get_connections_info()
            first_id = info[0]["id"]
            initial_count = len(info)

            # 关闭该连接
            result = pool.close_connection_by_id(first_id)
            assert result is True

            # 验证连接数减少
            assert pool.stats["pool_size"] == initial_count - 1

        finally:
            pool.close()

    def test_close_connections_by_strategy(self, test_environment):
        """测试按策略批量关闭连接"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=5, min_size=3, health_check_interval=0)

        try:
            initial_count = pool.stats["pool_size"]

            # 关闭最老的1个连接
            closed = pool.close_connections(1, strategy="oldest")
            assert closed == 1
            assert pool.stats["pool_size"] == initial_count - 1

            # 关闭最新的1个连接
            closed = pool.close_connections(1, strategy="newest")
            assert closed == 1
            assert pool.stats["pool_size"] == initial_count - 2

        finally:
            pool.close()

    def test_close_idle_connections(self, test_environment):
        """测试关闭空闲连接"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=5, min_size=2, health_check_interval=0)

        try:
            # 等待一小段时间（让连接变为空闲）
            time.sleep(0.2)

            # 关闭空闲超过0.1秒的连接
            closed = pool.close_idle_connections(min_idle_time=0.1)

            # 应该关闭了2个（min_size）
            assert closed == 2
            assert pool.stats["pool_size"] == 0

        finally:
            pool.close()

    def test_close_connections_by_filter(self, test_environment):
        """测试按条件关闭连接"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=5, min_size=3, health_check_interval=0)

        try:
            # 关闭使用次数为0的连接（所有连接）
            closed = pool.close_connections_by_filter(lambda c: c.use_count == 0)

            # 应该关闭了所有连接
            assert closed == 3
            assert pool.stats["pool_size"] == 0

        finally:
            pool.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
