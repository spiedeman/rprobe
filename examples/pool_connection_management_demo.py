#!/usr/bin/env python3
"""
连接池连接管理功能示例

演示如何：
1. 查看连接池中的所有连接信息
2. 关闭指定 ID 的连接
3. 关闭指定数量的连接（使用不同策略）
4. 关闭空闲时间过长的连接
5. 根据自定义条件关闭连接
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch
from src.pooling import ConnectionPool
from src.config.models import SSHConfig


def demo_connection_management():
    """演示连接管理功能"""
    print("=" * 70)
    print("连接池连接管理功能演示")
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
        print("\n1. 创建连接池（最小3个连接）")
        pool = ConnectionPool(config, max_size=5, min_size=3, health_check_interval=0)

        # 2. 查看连接信息
        print("\n2. 查看所有连接信息")
        connections = pool.get_connections_info()
        print(f"   总连接数: {len(connections)}")
        for conn in connections:
            print(f"   - ID: {conn['id']}, 状态: {conn['status']}, "
                  f"使用次数: {conn['use_count']}")

        # 3. 使用一些连接
        print("\n3. 获取2个连接使用")
        conns = []
        for i in range(2):
            cm = pool.get_connection()
            conn = cm.__enter__()
            conns.append((cm, conn))

        connections = pool.get_connections_info()
        idle_count = sum(1 for c in connections if c["status"] == "idle")
        in_use_count = sum(1 for c in connections if c["status"] == "in_use")
        print(f"   空闲连接: {idle_count}")
        print(f"   使用中: {in_use_count}")

        # 4. 关闭特定连接（无法关闭使用中的连接）
        print("\n4. 尝试关闭使用中的连接（会失败）")
        in_use_conn = [c for c in connections if c["status"] == "in_use"][0]
        result = pool.close_connection_by_id(in_use_conn["id"])
        print(f"   关闭结果: {result} (使用中的连接无法关闭)")

        # 释放连接
        for cm, conn in conns:
            cm.__exit__(None, None, None)
        print("   已释放使用中的连接")

        # 5. 关闭指定 ID 的连接
        print("\n5. 关闭指定 ID 的连接")
        connections = pool.get_connections_info()
        first_id = connections[0]["id"]
        print(f"   关闭连接: {first_id}")
        result = pool.close_connection_by_id(first_id)
        print(f"   关闭结果: {result}")
        print(f"   当前连接数: {pool.stats['pool_size']}")

        # 6. 按策略关闭连接
        print("\n6. 按策略关闭连接")

        # 6.1 关闭最老的1个连接
        print("   6.1 关闭最老的1个连接")
        closed = pool.close_connections(1, strategy="oldest")
        print(f"       关闭数量: {closed}")
        print(f"       当前连接数: {pool.stats['pool_size']}")

        # 添加更多连接用于后续测试
        pool.reset()
        print("\n   重置连接池，创建5个新连接")

        # 使用部分连接
        with pool.get_connection() as c1:
            with pool.get_connection() as c2:
                print(f"   使用2个连接")

        # 6.2 关闭最新的连接
        print("\n   6.2 关闭最新的1个连接")
        closed = pool.close_connections(1, strategy="newest")
        print(f"       关闭数量: {closed}")
        print(f"       当前连接数: {pool.stats['pool_size']}")

        # 6.3 关闭使用最少的连接
        print("\n   6.3 关闭使用最少的1个连接")
        closed = pool.close_connections(1, strategy="least_used")
        print(f"       关闭数量: {closed}")
        print(f"       当前连接数: {pool.stats['pool_size']}")

        # 7. 关闭空闲连接
        print("\n7. 关闭空闲时间超过0.1秒的连接")
        time.sleep(0.15)
        closed = pool.close_idle_connections(min_idle_time=0.1)
        print(f"   关闭数量: {closed}")
        print(f"   当前连接数: {pool.stats['pool_size']}")

        # 8. 根据自定义条件关闭
        print("\n8. 重置并测试自定义条件关闭")
        pool.reset()
        print(f"   重置后连接数: {pool.stats['pool_size']}")

        # 使用一些连接
        with pool.get_connection() as c:
            pass

        print("   关闭使用次数为0的连接")
        closed = pool.close_connections_by_filter(lambda c: c.use_count == 0)
        print(f"   关闭数量: {closed}")
        print(f"   当前连接数: {pool.stats['pool_size']}")

        # 9. 最终状态
        print("\n9. 最终连接信息")
        connections = pool.get_connections_info()
        for conn in connections:
            age = conn.get("age_seconds", 0)
            idle = conn.get("idle_seconds", 0)
            print(f"   - ID: {conn['id']}")
            print(f"     状态: {conn['status']}, 使用次数: {conn['use_count']}")
            print(f"     年龄: {age}s, 空闲: {idle}s")

        pool.close()

    print("\n" + "=" * 70)
    print("✓ 连接管理功能演示完成!")


if __name__ == "__main__":
    demo_connection_management()
