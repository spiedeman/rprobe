#!/usr/bin/env python3
"""
连接池复用和重置功能示例

演示如何：
1. 关闭连接池后保留对象并复用
2. 使用 reset() 方法重置连接池
3. 使用 PoolManager 管理连接池生命周期
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch
from src.pooling import ConnectionPool, PoolManager, get_pool_manager
from src.config.models import SSHConfig


def demo_pool_reset():
    """演示连接池重置功能"""
    print("=" * 70)
    print("连接池重置功能演示")
    print("=" * 70)

    config = SSHConfig(
        host="demo.example.com",
        username="demo",
        password="demo123",
        port=22,
    )

    with patch("src.pooling.ConnectionManager") as mock_conn_class:
        mock_conn = Mock()
        mock_conn.is_connected = True
        mock_conn_class.return_value = mock_conn

        # 1. 创建连接池
        print("\n1. 创建连接池")
        pool = ConnectionPool(config, max_size=3, min_size=2, health_check_interval=0)
        print(f"   连接池 ID: {id(pool)}")
        print(f"   初始连接数: {pool.stats['pool_size']}")
        print(f"   状态: {'运行中' if not pool._closed else '已关闭'}")

        # 2. 使用连接
        print("\n2. 获取并使用连接")
        with pool.get_connection() as conn:
            print(f"   获取连接成功")
            print(f"   当前连接数: {pool.stats['pool_size']}")
            print(f"   使用中: {pool.stats['in_use']}")

        # 3. 关闭连接池
        print("\n3. 关闭连接池")
        pool.close()
        print(f"   连接池已关闭")
        print(f"   当前连接数: {pool.stats['pool_size']}")
        print(f"   状态: {'运行中' if not pool._closed else '已关闭'}")

        # 4. 重置连接池
        print("\n4. 重置连接池（模拟新建）")
        pool.reset()
        print(f"   连接池已重置")
        print(f"   连接池 ID 不变: {id(pool)}")
        print(f"   新的连接数: {pool.stats['pool_size']}")
        print(f"   状态: {'运行中' if not pool._closed else '已关闭'}")

        # 5. 再次使用
        print("\n5. 再次使用连接池")
        with pool.get_connection() as conn:
            print(f"   获取连接成功")
            print(f"   当前连接数: {pool.stats['pool_size']}")

        # 6. 最终关闭
        print("\n6. 最终关闭")
        pool.close()
        print(f"   连接池已关闭")

    print("\n" + "=" * 70)


def demo_pool_manager():
    """演示连接池管理器功能"""
    print("\n" + "=" * 70)
    print("连接池管理器功能演示")
    print("=" * 70)

    config1 = SSHConfig(
        host="server1.example.com",
        username="user1",
        password="pass1",
        port=22,
    )

    config2 = SSHConfig(
        host="server2.example.com",
        username="user2",
        password="pass2",
        port=22,
    )

    with patch("src.pooling.ConnectionManager") as mock_conn_class:
        mock_conn = Mock()
        mock_conn.is_connected = True
        mock_conn_class.return_value = mock_conn

        # 获取管理器
        manager = get_pool_manager()

        # 1. 创建连接池
        print("\n1. 创建多个连接池")
        pool1 = manager.create_pool(config1, max_size=3, min_size=1, health_check_interval=0)
        pool2 = manager.create_pool(config2, max_size=3, min_size=1, health_check_interval=0)
        print(f"   连接池1 (server1): ID={id(pool1)}, 连接数={pool1.stats['pool_size']}")
        print(f"   连接池2 (server2): ID={id(pool2)}, 连接数={pool2.stats['pool_size']}")

        # 2. 复用连接池
        print("\n2. 复用相同配置的连接池")
        pool1_reuse = manager.create_pool(config1, max_size=3, min_size=1, health_check_interval=0)
        print(f"   相同对象: {pool1 is pool1_reuse}")
        print(f"   复用连接池: ID={id(pool1_reuse)}")

        # 3. 查看所有连接池
        print("\n3. 查看所有连接池")
        pools = manager.list_pools()
        print(f"   连接池列表: {pools}")
        stats = manager.get_all_stats()
        print(f"   统计信息: {len(stats)} 个连接池")

        # 4. 关闭单个连接池
        print("\n4. 关闭 server1 的连接池")
        manager.close_pool(config1)
        print(f"   server1 状态: {'运行中' if not pool1._closed else '已关闭'}")
        print(f"   server2 状态: {'运行中' if not pool2._closed else '已关闭'}")

        # 5. 重新激活已关闭的连接池
        print("\n5. 重新激活 server1 的连接池")
        pool1_new = manager.create_pool(config1, max_size=3, min_size=1, health_check_interval=0)
        print(f"   相同对象: {pool1 is pool1_new}")
        print(f"   状态: {'运行中' if not pool1_new._closed else '已关闭'}")
        print(f"   连接数: {pool1_new.stats['pool_size']}")

        # 6. 关闭所有连接池
        print("\n6. 关闭所有连接池（保留对象）")
        manager.close_all()
        print(f"   server1 状态: {'运行中' if not pool1._closed else '已关闭'}")
        print(f"   server2 状态: {'运行中' if not pool2._closed else '已关闭'}")
        print(f"   连接池数量: {len(manager.list_pools())}")

        # 7. 彻底移除
        print("\n7. 移除 server1 的连接池")
        manager.remove_pool(config1)
        print(f"   连接池数量: {len(manager.list_pools())}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    demo_pool_reset()
    demo_pool_manager()
    print("\n✓ 所有演示完成!")
