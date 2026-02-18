#!/usr/bin/env python3
"""
多 Shell 会话功能演示

展示如何使用 SSHClient 管理多个并发的 Shell 会话
"""
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_multiple_sessions():
    """演示多 Shell 会话功能"""
    print("=" * 60)
    print("多 Shell 会话功能演示")
    print("=" * 60)
    
    print("\n📋 功能特性:")
    print("-" * 60)
    print("1. 支持同时管理多个 Shell 会话")
    print("2. 每个会话有独立的 session_id")
    print("3. 可以为每个会话指定唯一标识")
    print("4. 支持设置默认会话（向后兼容）")
    print("5. 支持批量关闭所有会话")
    
    print("\n📖 API 说明:")
    print("-" * 60)
    
    print("""
# 打开多个会话（自动生成 session_id）
session_id1 = client.open_shell_session()
session_id2 = client.open_shell_session()

# 打开指定 session_id 的会话
session_id3 = client.open_shell_session(session_id="my-session")

# 在指定会话执行命令
result1 = client.shell_command("ls", session_id=session_id1)
result2 = client.shell_command("pwd", session_id=session_id2)

# 使用默认会话执行命令
result3 = client.shell_command("whoami")  # 使用默认会话

# 获取所有活跃会话
sessions = client.shell_sessions
print(f"活跃会话: {sessions}")

# 获取会话数量
count = client.shell_session_count
print(f"会话数量: {count}")

# 获取指定会话对象
session = client.get_shell_session(session_id1)

# 设置默认会话
client.set_default_shell_session(session_id2)

# 关闭指定会话
client.close_shell_session(session_id1)

# 关闭所有会话
client.close_all_shell_sessions()
    """)
    
    print("\n💡 使用场景:")
    print("-" * 60)
    print("• 同时操作多个远程目录")
    print("• 并行执行不同的命令序列")
    print("• 保持多个独立的工作环境")
    print("• 测试多个用户权限场景")
    
    print("\n✅ 向后兼容:")
    print("-" * 60)
    print("• 不传 session_id 时自动使用默认会话")
    print("• shell_session_active 属性仍然有效")
    print("• 单会话使用方式完全不变")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    demo_multiple_sessions()
