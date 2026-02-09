#!/usr/bin/env python3
"""
监控和日志示例

展示结构化日志和性能监控
"""
import time
from src import SSHClient, SSHConfig
from src.logging_config import configure_logging, get_logger


def example_1_simple_logging():
    """示例1: 简单日志配置"""
    print("=" * 60)
    print("示例1: 简单日志")
    print("=" * 60)
    
    # 配置简单格式日志
    configure_logging(level="INFO", format="simple")
    
    logger = get_logger(__name__)
    
    logger.debug("调试信息（不会显示）")
    logger.info("操作成功完成")
    logger.warning("这是一个警告")
    logger.error("这是一个错误")


def example_2_json_logging():
    """示例2: JSON格式日志"""
    print("=" * 60)
    print("示例2: JSON格式日志")
    print("=" * 60)
    
    import tempfile
    import json
    
    # 创建临时日志文件
    log_file = tempfile.mktemp(suffix='.log')
    
    # 配置JSON格式日志输出到文件
    configure_logging(
        level="INFO",
        format="json",
        output_file=log_file
    )
    
    logger = get_logger("test")
    
    # 记录结构化日志
    logger.info(
        "command_executed",
        command="ls -la",
        duration_ms=150,
        exit_code=0,
        host="server1"
    )
    
    logger.error(
        "command_failed",
        command="invalid_cmd",
        exit_code=127,
        error="Command not found"
    )
    
    # 读取并显示日志
    print(f"\n日志文件内容 ({log_file}):")
    with open(log_file) as f:
        for line in f:
            log_entry = json.loads(line)
            print(json.dumps(log_entry, indent=2))
    
    import os
    os.unlink(log_file)


def example_3_context_logging():
    """示例3: 上下文绑定日志"""
    print("=" * 60)
    print("示例3: 上下文绑定日志")
    print("=" * 60)
    
    configure_logging(level="INFO", format="colored")
    
    logger = get_logger("app")
    
    # 绑定上下文信息
    context_logger = logger.bind(
        request_id="abc123",
        user="admin",
        host="web-01"
    )
    
    # 所有日志都自动包含上下文
    context_logger.info("开始处理请求")
    context_logger.info("执行数据库查询")
    context_logger.info("请求处理完成", duration_ms=245)


def example_4_performance_monitoring():
    """示例4: 性能监控"""
    print("=" * 60)
    print("示例4: 性能监控")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-user",
        password="your-pass"
    )
    
    print("\n1. 测试不同数据接收模式...")
    
    # 不同的接收模式
    modes = ["select", "adaptive", "original"]
    
    for mode in modes:
        try:
            config.recv_mode = mode
            
            with SSHClient(config) as client:
                start = time.time()
                
                # 执行命令
                for i in range(3):
                    client.exec_command(f"echo 'Test {i}'")
                
                elapsed = time.time() - start
                
                print(f"  {mode:12s}: {elapsed:.3f}s")
        except Exception as e:
            print(f"  {mode:12s}: 失败 - {e}")


def example_5_connection_pool_stats():
    """示例5: 连接池统计监控"""
    print("=" * 60)
    print("示例5: 连接池统计")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-user",
        password="your-pass"
    )
    
    # 创建连接池
    client = SSHClient(config, use_pool=True, max_size=5, min_size=2)
    
    print("\n初始状态:")
    print_pool_stats(client)
    
    # 执行一些命令
    for i in range(5):
        client.exec_command(f"echo 'Command {i}'")
    
    print("\n执行5个命令后:")
    print_pool_stats(client)
    
    # 再执行更多命令
    for i in range(10):
        client.exec_command(f"echo 'More {i}'")
    
    print("\n执行15个命令后:")
    print_pool_stats(client)
    
    client.disconnect()


def print_pool_stats(client):
    """打印连接池统计"""
    if hasattr(client, '_pool') and client._pool:
        stats = client._pool.stats
        print(f"  总连接数: {stats['total']}")
        print(f"  空闲连接: {stats['pool_size']}")
        print(f"  使用中: {stats['in_use']}")
        print(f"  创建的连接: {stats['created']}")
        print(f"  复用的连接: {stats['reused']}")
        
        if stats['created'] > 0:
            reuse_ratio = stats['reused'] / stats['created']
            print(f"  复用率: {reuse_ratio:.1f}")


def example_6_benchmark():
    """示例6: 基准测试"""
    print("=" * 60)
    print("示例6: 基准测试")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-user",
        password="your-pass"
    )
    
    print("\n测试命令执行性能:")
    
    # 无连接池
    start = time.time()
    for _ in range(5):
        with SSHClient(config, use_pool=False) as client:
            client.exec_command("echo 'test'")
    no_pool_time = time.time() - start
    
    # 有连接池
    client = SSHClient(config, use_pool=True, max_size=5)
    start = time.time()
    for _ in range(5):
        client.exec_command("echo 'test'")
    with_pool_time = time.time() - start
    client.disconnect()
    
    print(f"  无连接池: {no_pool_time:.3f}s")
    print(f"  有连接池: {with_pool_time:.3f}s")
    
    if with_pool_time > 0:
        speedup = no_pool_time / with_pool_time
        print(f"  性能提升: {speedup:.1f}倍")


if __name__ == "__main__":
    print("监控和日志示例\n")
    
    # 取消注释要运行的示例
    # example_1_simple_logging()
    # example_2_json_logging()
    # example_3_context_logging()
    # example_4_performance_monitoring()
    # example_5_connection_pool_stats()
    # example_6_benchmark()
    
    print("\n示例完成！请根据实际需求修改配置。")
