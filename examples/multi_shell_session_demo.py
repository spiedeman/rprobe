#!/usr/bin/env python3
"""
多 Shell 会话管理示例

演示如何在单个 SSH 连接上管理多个独立的 Shell 会话。
每个会话都有自己的工作目录和环境变量，完全独立。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rprobe.core.connection import ConnectionManager, MultiSessionManager
from rprobe.config.models import SSHConfig


def demo_multi_session():
    """演示多会话功能"""
    print("=" * 70)
    print("多 Shell 会话管理演示")
    print("=" * 70)
    print()
    print("说明：单个 SSH 连接可以打开多个独立的 Shell 会话")
    print("每个会话都有自己的 channel，状态完全独立")
    print()

    # 配置
    config = SSHConfig(
        host="demo.example.com",
        username="demo",
        password="demo123",
        port=22,
        command_timeout=30.0,
    )

    # 建立连接
    print("1. 建立 SSH 连接")
    conn = ConnectionManager(config)
    # conn.connect()  # 实际使用时取消注释
    print("   ✓ 连接已建立")

    # 创建多会话管理器
    print("\n2. 创建多会话管理器")
    session_mgr = MultiSessionManager(conn, config)
    print("   ✓ 管理器已创建")

    # 创建多个会话
    print("\n3. 创建多个 Shell 会话")
    print("   3.1 创建 session1（默认 shell）")
    # session1 = session_mgr.create_session("session1")
    print("   3.2 创建 session2（用于 /tmp 目录操作）")
    # session2 = session_mgr.create_session("session2")
    print("   3.3 创建 session3（用于 python 交互）")
    # session3 = session_mgr.create_session("session3")
    print("   ✓ 已创建 3 个独立会话")

    print("\n4. 各会话独立执行命令")
    print("   会话1: pwd")
    # output1 = session1.execute_command("pwd")
    # print(f"   输出: {output1}")  # /home/demo

    print("   会话2: cd /tmp && pwd")
    # output2 = session2.execute_command("cd /tmp && pwd")
    # print(f"   输出: {output2}")  # /tmp

    print("   会话3: pwd")
    # output3 = session3.execute_command("pwd")
    # print(f"   输出: {output3}")  # /home/demo (未改变)

    print("   会话1 再次执行: pwd")
    # output4 = session1.execute_command("pwd")
    # print(f"   输出: {output4}")  # /home/demo (仍然未改变)

    print("\n5. 会话状态管理")
    print(f"   活跃会话数: 3")
    print(f"   会话列表: ['session1', 'session2', 'session3']")

    print("\n6. 获取会话信息")
    print("   session1 信息:")
    print("     - 会话ID: session1")
    print("     - 是否活跃: True")
    print("     - 命令数: 2")
    print("     - 年龄: 5.2s")

    print("\n7. 关闭特定会话")
    print("   关闭 session2")
    # session_mgr.close_session("session2")
    print("   ✓ session2 已关闭")
    print(f"   剩余活跃会话: 2")

    print("\n8. 在剩余会话中继续操作")
    print("   session1: ls -la")
    print("   session3: python3 --version")

    print("\n9. 关闭所有会话")
    # session_mgr.close_all_sessions()
    print("   ✓ 所有会话已关闭")

    print("\n10. 断开连接")
    # conn.disconnect()
    print("    ✓ 连接已断开")

    print("\n" + "=" * 70)
    print("关键特性:")
    print("- 一个 SSH 连接可以创建多个 Shell 会话")
    print("- 每个会话独立维护自己的状态（工作目录、环境变量等）")
    print("- 会话可以单独创建、使用和关闭")
    print("- 关闭一个会话不影响其他会话")
    print("- 适用于需要同时维护多个独立环境的场景")
    print("=" * 70)


if __name__ == "__main__":
    demo_multi_session()
