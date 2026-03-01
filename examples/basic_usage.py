#!/usr/bin/env python3
"""
基本用法示例

展示SSHClient的核心功能
"""
from src import SSHClient, SSHConfig


def example_1_basic_command():
    """示例1: 执行基本命令"""
    print("=" * 60)
    print("示例1: 执行基本命令")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-username",
        password="your-password"
    )
    
    with SSHClient(config) as client:
        # 执行简单命令
        result = client.exec_command("uname -a")
        print(f"命令: uname -a")
        print(f"退出码: {result.exit_code}")
        print(f"输出: {result.stdout}")
        print(f"执行时间: {result.execution_time:.2f}ms\n")


def example_2_with_pool():
    """示例2: 使用连接池"""
    print("=" * 60)
    print("示例2: 使用连接池")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-username",
        password="your-password"
    )
    
    # 启用连接池
    client = SSHClient(config, use_pool=True, max_size=5)
    
    try:
        # 执行多个命令（自动复用连接）
        commands = [
            "echo 'Command 1'",
            "echo 'Command 2'",
            "echo 'Command 3'"
        ]
        
        for cmd in commands:
            result = client.exec_command(cmd)
            print(f"✓ {cmd}")
        
        # 查看连接池统计
        stats = client._pool.stats
        print(f"\n连接池统计:")
        print(f"  - 创建: {stats['created']}")
        print(f"  - 复用: {stats['reused']}")
        
    finally:
        client.disconnect()


def example_3_error_handling():
    """示例3: 错误处理"""
    print("=" * 60)
    print("示例3: 错误处理")
    print("=" * 60)
    
    from rprobe.exceptions import CommandTimeoutError
    
    config = SSHConfig(
        host="localhost",
        username="your-username",
        password="your-password",
        command_timeout=5.0  # 5秒超时
    )
    
    try:
        with SSHClient(config) as client:
            # 会超时的命令
            result = client.exec_command("sleep 10")
    except CommandTimeoutError as e:
        print(f"✓ 捕获超时异常: {e}")
    except Exception as e:
        print(f"✗ 其他异常: {e}")


def example_4_shell_session():
    """示例4: Shell会话"""
    print("=" * 60)
    print("示例4: Shell会话")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-username",
        password="your-password"
    )
    
    with SSHClient(config) as client:
        # 打开交互式Shell
        prompt = client.open_shell_session()
        print(f"检测到提示符: {prompt}")
        
        # 在Shell中执行命令（保持状态）
        client.shell_command("cd /tmp")
        result = client.shell_command("pwd")
        print(f"当前目录: {result.stdout.strip()}")
        
        client.shell_command("export MY_VAR='Hello'")
        result = client.shell_command("echo $MY_VAR")
        print(f"环境变量: {result.stdout.strip()}")
        
        client.close_shell_session()


if __name__ == "__main__":
    print("RemoteSSH 基本用法示例")
    print("注意: 请修改配置中的主机、用户名和密码\n")
    
    # 取消注释要运行的示例
    # example_1_basic_command()
    # example_2_with_pool()
    # example_3_error_handling()
    # example_4_shell_session()
    
    print("\n示例完成！请根据实际需求修改配置。")
