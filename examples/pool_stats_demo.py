#!/usr/bin/env python3
"""
连接池统计信息展示示例
"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import Mock, patch
from src.pooling import ConnectionPool
from src.config.models import SSHConfig


def demo_pool_stats():
    """演示连接池统计功能"""
    print("=" * 70)
    print("连接池统计信息展示")
    print("=" * 70)

    config = SSHConfig(
        host="test.example.com",
        username="testuser",
        password="testpass123",
        port=22,
        timeout=5.0,
        command_timeout=10.0,
    )

    print("\n1. 创建连接池...")
    with patch('src.pooling.ConnectionManager') as mock_conn_class:
        # Mock 连接
        mock_conn = Mock()
        mock_conn.is_connected = True
        mock_conn_class.return_value = mock_conn

        pool = ConnectionPool(
            config,
            max_size=5,
            min_size=3,
            parallel_init=True
        )

        print(f"   ✓ 连接池创建完成")

        # 显示初始统计
        print("\n2. 初始统计信息:")
        stats = pool.stats
        print(f"   - 总连接数: {stats['total']}")
        print(f"   - 池中连接: {stats['pool_size']}")
        print(f"   - 使用中的连接: {stats['in_use']}")
        print(f"   - 最大连接数: {stats['max_size']}")
        print(f"   - 创建时间: {stats['created_at']}")

        # 模拟获取和释放连接
        print("\n3. 模拟获取连接...")
        with pool.get_connection() as conn1:
            print("   ✓ 获取连接 1")

            with pool.get_connection() as conn2:
                print("   ✓ 获取连接 2")

                # 显示使用中的统计
                print("\n4. 使用中的统计:")
                stats = pool.stats
                print(f"   - 池中连接: {stats['pool_size']}")
                print(f"   - 使用中的连接: {stats['in_use']}")
                print(f"   - 使用率: {stats['utilization_rate']}%")
                print(f"   - 连接池利用率: {stats['pool_usage_rate']}%")

            print("   ✓ 释放连接 2")

        print("   ✓ 释放连接 1")

        # 显示完整统计
        print("\n5. 完整统计信息:")
        stats = pool.stats
        print(f"\n   基础统计:")
        print(f"   - 创建的连接: {stats['created']}")
        print(f"   - 复用的连接: {stats['reused']}")
        print(f"   - 关闭的连接: {stats['closed']}")
        print(f"   - 过期的连接: {stats['expired']}")
        print(f"   - 失败的连接: {stats['failed']}")

        print(f"\n   使用率:")
        print(f"   - 使用中占比: {stats['utilization_rate']}%")
        print(f"   - 总连接占比: {stats['pool_usage_rate']}%")

        print(f"\n   等待统计:")
        print(f"   - 等待次数: {stats['waits']}")
        print(f"   - 平均等待时间: {stats['avg_wait_time']}")
        print(f"   - 总等待时间: {stats['total_wait_time']}")

        print(f"\n   性能指标:")
        print(f"   - 平均获取时间: {stats['avg_acquire_time']}")
        print(f"   - 最大获取时间: {stats['max_acquire_time']}")
        print(f"   - 获取次数: {stats['acquire_count']}")

        print(f"\n   时间信息:")
        print(f"   - 运行时间: {stats['uptime']}")
        print(f"   - 创建时间: {stats['created_at']}")
        print(f"   - 最后活动: {stats['last_activity']}")

        print(f"\n   派生指标:")
        print(f"   - 初始化成功率: {stats.get('init_success_rate', 0)}%")
        print(f"   - 健康检查通过率: {stats.get('health_check_rate', 0)}%")
        print(f"   - 连接复用率: {stats.get('reuse_rate', 0)}%")
        print(f"   - 平均连接生命周期: {stats.get('avg_lifetime', 0):.2f}s")
        print(f"   - 峰值并发连接: {stats.get('peak_in_use', 0)}")

        # 关闭连接池
        print("\n6. 关闭连接池...")
        pool.close()
        print("   ✓ 连接池已关闭")

        # 显示关闭后的统计
        print("\n7. 关闭后的统计:")
        stats = pool.stats
        print(f"   - 已关闭: {stats['closed']}")
        print(f"   - 总连接数: {stats['total']}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    demo_pool_stats()
