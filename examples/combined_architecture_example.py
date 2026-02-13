#!/usr/bin/env python3
"""
方式3: 组合使用 - 连接池 + 每个连接支持多Shell

最佳实践：结合两种架构的优势
- 连接池提供：并发能力、故障隔离、负载均衡
- 多会话提供：状态隔离、资源节省
"""
from src.pooling import ConnectionPool
from src.core.connection import MultiSessionManager
from src.config.models import SSHConfig

# 配置
config = SSHConfig(
    host="example.com",
    username="user",
    password="pass",
    port=22,
)

# 创建连接池
pool = ConnectionPool(
    config,
    max_size=3,      # 3个TCP连接
    min_size=2,
)

print("=== 组合架构：连接池 + 每个连接多Shell ===\n")

# 从池中获取连接，每个连接创建多个会话
with pool.get_connection() as conn1:
    # 在连接1上创建2个会话
    mgr1 = MultiSessionManager(conn1, config)
    
    build_session = mgr1.create_session("build")
    test_session = mgr1.create_session("test")
    
    print("连接1上的会话:")
    print(f"  - build: 编译项目")
    print(f"  - test: 运行测试")
    
    # 执行命令
    build_session.execute_command("cd /project && make")
    test_session.execute_command("cd /project && make test")

with pool.get_connection() as conn2:
    # 在连接2上创建2个会话
    mgr2 = MultiSessionManager(conn2, config)
    
    deploy_session = mgr2.create_session("deploy")
    monitor_session = mgr2.create_session("monitor")
    
    print("\n连接2上的会话:")
    print(f"  - deploy: 部署应用")
    print(f"  - monitor: 监控服务")

print("\n架构优势:")
print(f"  • TCP连接数: 2 (节省资源)")
print(f"  • 独立会话数: 4 (状态隔离)")
print(f"  • 并发能力: 2连接并行 × 2会话 = 4个并发环境")

# 查看池状态
stats = pool.stats
print(f"\n池状态:")
print(f"  总连接: {stats['total']}")
print(f"  池中: {stats['pool_size']}")
print(f"  使用中: {stats['in_use']}")

# 清理
pool.close()

print("\n✓ 组合使用示例完成")
print("\n适用场景:")
print("  • 微服务部署流水线")
print("  • CI/CD 构建系统")
print("  • 多环境并行开发")
print("  • 需要平衡并发与资源的场景")
