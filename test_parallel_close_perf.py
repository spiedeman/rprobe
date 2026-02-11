#!/usr/bin/env python3
"""
验证连接池并行关闭性能的测试脚本
"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import Mock, patch
from src.pooling import ConnectionPool, PooledConnection
from src.config.models import SSHConfig
from src.core.connection import ConnectionManager


def test_parallel_close_performance():
    """测试并行关闭性能"""
    print("=" * 60)
    print("连接池并行关闭性能测试")
    print("=" * 60)
    
    config = SSHConfig(
        host="test.example.com",
        username="testuser",
        password="testpass123",
        port=22,
        timeout=5.0,
        command_timeout=10.0,
    )
    
    print("\n1. 创建包含10个连接的连接池...")
    
    # Mock ConnectionManager 避免实际连接
    with patch('src.pooling.ConnectionManager') as mock_conn_class:
        mock_connections = []
        for i in range(10):
            mock_conn = Mock(spec=ConnectionManager)
            mock_conn.is_connected = True
            mock_connections.append(mock_conn)
        
        mock_conn_class.side_effect = mock_connections
        
        # 创建连接池
        pool = ConnectionPool(
            config,
            max_size=10,
            min_size=10,
            parallel_init=True
        )
        
        print(f"   ✓ 连接池创建完成: {pool.stats['total']} 个连接")
        
        # 模拟关闭耗时
        def slow_close():
            # 模拟 paramiko 关闭耗时 0.5 秒
            time.sleep(0.5)
        
        for conn in pool._pool:
            conn.close = Mock(side_effect=slow_close)
        
        print("\n2. 执行并行关闭...")
        start = time.time()
        pool.close(timeout=5.0)
        elapsed = time.time() - start
        
        print(f"   ✓ 关闭完成")
        print(f"   - 总耗时: {elapsed:.2f} 秒")
        print(f"   - 平均每个连接: {elapsed/10:.2f} 秒")
        
        # 验证性能
        if elapsed < 3.0:
            print(f"\n   ✅ 性能优秀！并行关闭有效（期望 <3s，实际 {elapsed:.2f}s）")
        elif elapsed < 6.0:
            print(f"\n   ⚠️  性能一般（期望 <3s，实际 {elapsed:.2f}s）")
        else:
            print(f"\n   ❌ 性能较差，可能是串行关闭（期望 <3s，实际 {elapsed:.2f}s）")
        
        # 计算理论值
        print(f"\n3. 性能对比:")
        print(f"   串行关闭（理论）: 10 × 0.5s = 5.0s")
        print(f"   并行关闭（理论）: ~0.5s")
        print(f"   实际关闭: {elapsed:.2f}s")
        
        if elapsed < 5.0:
            speedup = 5.0 / elapsed
            print(f"   提升倍数: {speedup:.1f}x")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_parallel_close_performance()
