#!/usr/bin/env python3
"""
方式2: 单连接 + 多Shell 使用示例
"""
from rprobe.core.connection import ConnectionManager, MultiSessionManager
from rprobe.config.models import SSHConfig

# 配置
config = SSHConfig(
    host="example.com",
    username="user",
    password="pass",
    port=22,
)

# 创建单连接
conn = ConnectionManager(config)
conn.connect()

# 创建多会话管理器
mgr = MultiSessionManager(conn, config)

# 创建多个独立会话
session1 = mgr.create_session("workspace1")  # 默认目录
session2 = mgr.create_session("workspace2")  # 将切换到 /tmp
session3 = mgr.create_session("ipython")     # 将启动ipython

# 各会话完全独立
output1 = session1.execute_command("pwd")           # /home/user
output2 = session2.execute_command("cd /tmp && pwd") # /tmp
output3 = session1.execute_command("pwd")           # /home/user (目录未变！)

print(f"会话1目录: {output1}")
print(f"会话2目录: {output2}")
print(f"会话1再次查看: {output3}")

# 管理会话
print(f"\n活跃会话: {mgr.list_sessions()}")
print(f"会话数: {mgr.active_session_count}")

# 获取会话信息
info = mgr.get_session_info("workspace1")
print(f"\n会话1信息:")
print(f"  命令数: {info['command_count']}")
print(f"  年龄: {info['age_seconds']:.1f}s")

# 关闭特定会话
mgr.close_session("workspace2")
print(f"\n关闭后活跃会话: {mgr.list_sessions()}")

# 关闭所有会话
mgr.close_all_sessions()

# 断开连接
conn.disconnect()
