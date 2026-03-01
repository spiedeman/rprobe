#!/usr/bin/env python3
"""
连接池+单Shell vs 单连接+多Shell 性能对比测试

此测试展示两种架构在实际使用中的差异。
"""
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch, MagicMock
from rprobe.pooling import ConnectionPool
from rprobe.core.connection import ConnectionManager, MultiSessionManager
from rprobe.session.shell_session import ShellSession
from rprobe.config.models import SSHConfig


def mock_ssh_setup():
    """设置SSH mock"""
    mock_client = MagicMock()
    mock_transport = MagicMock()
    mock_client.get_transport.return_value = mock_transport
    mock_transport.is_active.return_value = True
    
    mock_channel = MagicMock()
    mock_channel.get_id.return_value = 1
    mock_channel.closed = False
    mock_channel.recv_ready.return_value = False
    mock_transport.open_session.return_value = mock_channel
    
    return mock_client, mock_transport, mock_channel


def benchmark_connection_pool():
    """测试连接池+单Shell性能"""
    print("=" * 70)
    print("架构A：连接池 + 单Shell会话")
    print("=" * 70)
    
    config = SSHConfig(
        host="test.example.com",
        username="testuser",
        password="testpass",
        port=22,
    )
    
    with patch('paramiko.SSHClient') as mock_client_class:
        mock_client, mock_transport, mock_channel = mock_ssh_setup()
        mock_client_class.return_value = mock_client
        
        # 模拟连接建立耗时
        def mock_connect(*args, **kwargs):
            time.sleep(0.1)  # 模拟100ms连接耗时
        
        mock_client.connect.side_effect = mock_connect
        
        print("\n1. 创建连接池（3个连接）")
        start = time.time()
        pool = ConnectionPool(config, max_size=3, min_size=3, health_check_interval=0)
        init_time = time.time() - start
        print(f"   初始化耗时: {init_time:.3f}s")
        print(f"   连接数: {pool.stats['pool_size']}")
        
        print("\n2. 并发执行命令（模拟）")
        start = time.time()
        
        def execute_task(conn_id):
            with pool.get_connection() as conn:
                # 模拟命令执行
                time.sleep(0.05)
                return conn_id
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(execute_task, i) for i in range(3)]
            results = [f.result() for f in futures]
        
        exec_time = time.time() - start
        print(f"   3个命令并发耗时: {exec_time:.3f}s")
        print(f"   平均每个命令: {exec_time/3:.3f}s")
        
        print("\n3. 资源占用估算")
        print(f"   TCP连接数: 3")
        print(f"   内存占用: ~30MB (约10MB/连接)")
        print(f"   服务器连接数: 3")
        
        pool.close()
        
        return {
            "init_time": init_time,
            "exec_time": exec_time,
            "connections": 3,
            "memory_mb": 30,
        }


def benchmark_multi_session():
    """测试单连接+多Shell性能"""
    print("\n" + "=" * 70)
    print("架构B：单连接 + 多Shell会话")
    print("=" * 70)
    
    config = SSHConfig(
        host="test.example.com",
        username="testuser",
        password="testpass",
        port=22,
    )
    
    with patch('paramiko.SSHClient') as mock_client_class, \
         patch.object(ShellSession, '__init__', return_value=None), \
         patch.object(ShellSession, 'initialize', return_value="$"):
        
        mock_client, mock_transport, mock_channel = mock_ssh_setup()
        mock_client_class.return_value = mock_client
        
        # 模拟连接建立耗时
        def mock_connect(*args, **kwargs):
            time.sleep(0.1)  # 模拟100ms连接耗时
        
        mock_client.connect.side_effect = mock_connect
        
        print("\n1. 创建单连接 + 3个Shell会话")
        start = time.time()
        conn = ConnectionManager(config)
        conn.connect()
        connect_time = time.time() - start
        
        mgr = MultiSessionManager(conn, config)
        
        # 创建3个会话（每个channel创建很快）
        sessions = []
        for i in range(3):
            mock_ch = MagicMock()
            mock_ch.get_id.return_value = i + 1
            mock_transport.open_session.return_value = mock_ch
            sess = mgr.create_session(f"session{i+1}")
            sessions.append(sess)
        
        init_time = time.time() - start
        print(f"   初始化耗时: {init_time:.3f}s")
        print(f"   连接数: 1")
        print(f"   会话数: {mgr.active_session_count}")
        
        print("\n2. 执行命令（模拟）")
        start = time.time()
        
        # 单连接上的命令是串行的
        for i, session in enumerate(sessions):
            # 模拟命令执行
            time.sleep(0.05)
        
        exec_time = time.time() - start
        print(f"   3个命令串行耗时: {exec_time:.3f}s")
        print(f"   平均每个命令: {exec_time/3:.3f}s")
        print(f"   注意：实际并发需要线程调度，可能有交错")
        
        print("\n3. 资源占用估算")
        print(f"   TCP连接数: 1")
        print(f"   内存占用: ~10MB (共享transport)")
        print(f"   服务器连接数: 1")
        print(f"   Channel数: 3")
        
        conn.disconnect()
        
        return {
            "init_time": init_time,
            "exec_time": exec_time,
            "connections": 1,
            "memory_mb": 10,
        }


def print_comparison(results_a, results_b):
    """打印对比结果"""
    print("\n" + "=" * 70)
    print("性能对比总结")
    print("=" * 70)
    
    print(f"\n{'指标':<25} {'连接池+单Shell':<20} {'单连接+多Shell':<20}")
    print("-" * 70)
    print(f"{'初始化耗时':<25} {results_a['init_time']:.3f}s{'':<14} {results_b['init_time']:.3f}s")
    print(f"{'命令执行耗时(3个)':<25} {results_a['exec_time']:.3f}s{'':<14} {results_b['exec_time']:.3f}s")
    print(f"{'TCP连接数':<25} {results_a['connections']:<20} {results_b['connections']:<20}")
    print(f"{'内存占用(估算)':<25} {results_a['memory_mb']}MB{'':<17} {results_b['memory_mb']}MB")
    
    print("\n" + "-" * 70)
    print("关键差异:")
    print(f"  • 初始化速度: 单连接+多Shell 快 {results_a['init_time']/results_b['init_time']:.1f}x")
    print(f"  • 并发能力: 连接池真正并行，多Shell串行执行")
    print(f"  • 资源消耗: 连接池使用 {results_a['connections']/results_b['connections']:.0f}x TCP连接")
    print(f"  • 内存占用: 连接池使用 {results_a['memory_mb']/results_b['memory_mb']:.0f}x 内存")
    
    print("\n选择建议:")
    print("  ✓ 需要真正并行处理 → 使用连接池")
    print("  ✓ 需要状态隔离+节省资源 → 使用单连接+多Shell")
    print("  ✓ 两者都要 → 连接池(每个连接支持多Shell)")
    print("=" * 70)


def demo_use_cases():
    """演示不同使用场景"""
    print("\n" + "=" * 70)
    print("使用场景对比")
    print("=" * 70)
    
    print("""
场景1: 批量文件传输（100个文件）
─────────────────────────────────────────────────────────────────────
连接池方案:
  代码: with pool.get_connection() as conn:
           for file in files:
               executor.submit(upload_file, conn, file)
  特点: 10个连接并发上传，速度快
  缺点: 占用10个服务器连接

单连接+多Shell方案:
  代码: sessions = [mgr.create_session() for _ in range(10)]
           for i, file in enumerate(files):
               sessions[i % 10].execute(f"scp {file} ...")
  特点: 1个连接复用，节省资源
  缺点: 串行执行，速度慢

场景2: 多项目并行开发
─────────────────────────────────────────────────────────────────────
连接池方案:
  每个开发者使用独立连接
  → 成本高，没必要

单连接+多Shell方案:
  mgr.create_session("project_a")  # cd /project_a
  mgr.create_session("project_b")  # cd /project_b
  mgr.create_session("project_c")  # cd /project_c
  → 状态保持，切换方便

场景3: 微服务部署流水线
─────────────────────────────────────────────────────────────────────
混合方案（推荐）:
  pool = ConnectionPool(max_size=3)
  
  # 3个连接，每个连接2个会话
  with pool.get_connection() as conn1:
      mgr1 = MultiSessionManager(conn1, config)
      build_session = mgr1.create_session("build")
      test_session = mgr1.create_session("test")
  
  with pool.get_connection() as conn2:
      mgr2 = MultiSessionManager(conn2, config)
      deploy_session = mgr2.create_session("deploy")
      monitor_session = mgr2.create_session("monitor")
  
  → 3个TCP连接，6个独立会话环境
  → 并行能力与资源消耗的最佳平衡
""")


if __name__ == "__main__":
    print("SSH 连接架构性能对比测试")
    print("模拟环境：创建3个执行环境，执行简单命令")
    
    # 运行测试
    results_a = benchmark_connection_pool()
    results_b = benchmark_multi_session()
    
    # 打印对比
    print_comparison(results_a, results_b)
    
    # 演示使用场景
    demo_use_cases()
    
    print("\n✓ 测试完成!")
