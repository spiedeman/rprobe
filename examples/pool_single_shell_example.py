#!/usr/bin/env python3
"""
方式1: 连接池 + 单Shell 使用示例
"""
from rprobe.pooling import ConnectionPool, get_pool_manager
from rprobe.session.shell_session import ShellSession
from rprobe.config.models import SSHConfig

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
    max_size=5,      # 最大5个连接
    min_size=2,      # 保持2个连接
    max_idle=300,    # 5分钟空闲超时
    max_age=3600,    # 1小时最大寿命
)

# 使用连接池 - 每个连接一个Shell
with pool.get_connection() as conn:
    # 获取连接后创建ShellSession
    channel = conn.open_channel()
    shell = ShellSession(channel, config)
    shell.initialize()
    
    # 执行命令
    output = shell.execute_command("pwd")
    print(f"输出: {output}")
    
    # 关闭shell（连接归还到池中）
    shell.close()

# 查看池状态
stats = pool.stats
print(f"池大小: {stats['pool_size']}, 使用中: {stats['in_use']}")

# 关闭连接池
pool.close()
