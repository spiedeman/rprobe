#!/usr/bin/env python3
"""
连接池并行关闭功能演示

展示如何使用 ConnectionPool 的并行关闭特性来快速关闭多个连接
"""
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_parallel_close():
    """演示连接池并行关闭功能"""
    print("=" * 70)
    print("连接池并行关闭功能演示")
    print("=" * 70)
    
    print("\n📋 功能特性:")
    print("-" * 70)
    print("1. 使用 ThreadPoolExecutor 并发关闭连接")
    print("2. 最大并发数限制为 10，避免资源耗尽")
    print("3. 支持单个连接超时控制")
    print("4. 异常处理和错误统计")
    print("5. 详细的关闭日志记录")
    
    print("\n💡 性能对比:")
    print("-" * 70)
    print("假设有 10 个连接，每个关闭耗时 100ms:")
    print("  串行关闭: 10 × 100ms = 1000ms")
    print("  并行关闭: ~100ms (理论上)")
    print("  性能提升: ~10 倍")
    
    print("\n🔧 使用示例:")
    print("-" * 70)
    print("""
from src import SSHClient, SSHConfig
from rprobe.pooling import ConnectionPool

# 创建配置
config = SSHConfig(
    host="example.com",
    username="user",
    password="pass"
)

# 使用连接池创建多个连接
pool = ConnectionPool(
    config,
    max_size=10,
    min_size=5,
    parallel_init=True  # 并行初始化连接
)

# 使用连接池执行操作...
with pool.get_connection() as conn:
    # 执行命令
    pass

# 退出时自动并行关闭所有连接
# 或者手动关闭
pool.close(timeout=5.0)
    """)
    
    print("\n⚙️  代码实现:")
    print("-" * 70)
    print("""
def _close_connections_parallel(
    self, 
    connections: List[PooledConnection], 
    timeout: float
) -> None:
    \"\"\"并行关闭连接\"\"\"
    if not connections:
        return
    
    # 限制并发线程数
    max_workers = min(len(connections), 10)
    failed_count = 0
    
    def close_single_connection(pooled: PooledConnection) -> None:
        \"\"\"关闭单个连接\"\"\"
        try:
            pooled.close()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
            raise
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有关闭任务
        future_to_conn = {
            executor.submit(close_single_connection, conn): conn 
            for conn in connections
        }
        
        # 等待所有任务完成
        for future in future_to_conn:
            try:
                future.result(timeout=...)
            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to close connection: {e}")
    """)
    
    print("\n📊 日志输出示例:")
    print("-" * 70)
    print("""
2024-01-20 10:30:00,123 - src.pooling - INFO - Closing connection pool for example.com
2024-01-20 10:30:00,234 - src.pooling - WARNING - Failed to close connection: Connection reset
2024-01-20 10:30:00,245 - src.pooling - WARNING - Failed to close 1/10 connections
2024-01-20 10:30:00,246 - src.pooling - INFO - Connection pool closed for example.com
    """)
    
    print("\n✅ 优势:")
    print("-" * 70)
    print("• 快速关闭: 多个连接同时关闭，大幅减少等待时间")
    print("• 资源回收: 及时释放 SSH 连接和系统资源")
    print("• 容错处理: 单个连接关闭失败不影响其他连接")
    print("• 超时控制: 防止连接关闭阻塞整个进程")
    print("• 日志记录: 清晰的关闭过程和错误信息")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    demo_parallel_close()
