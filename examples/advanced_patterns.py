#!/usr/bin/env python3
"""
高级模式示例

展示高级用法和最佳实践
"""
import time
from contextlib import contextmanager
from typing import List

from src import SSHClient, SSHConfig
from src.pooling import get_pool_manager


@contextmanager
def timed_operation(name: str):
    """上下文管理器：计时操作"""
    start = time.time()
    print(f"[{name}] 开始...")
    try:
        yield
    finally:
        elapsed = time.time() - start
        print(f"[{name}] 完成，耗时: {elapsed:.3f}s\n")


def example_1_connection_context_manager():
    """示例1: 连接上下文管理器"""
    print("=" * 60)
    print("示例1: 连接上下文管理器")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-user",
        password="your-pass"
    )
    
    # 方法1: 使用 with 语句（推荐）
    with SSHClient(config) as client:
        result = client.exec_command("whoami")
        print(f"当前用户: {result.stdout.strip()}")
    # 连接自动关闭
    
    # 方法2: 显式关闭
    client = SSHClient(config)
    try:
        result = client.exec_command("pwd")
        print(f"当前目录: {result.stdout.strip()}")
    finally:
        client.disconnect()


def example_2_command_pipeline():
    """示例2: 命令管道"""
    print("=" * 60)
    print("示例2: 命令管道")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-user",
        password="your-pass"
    )
    
    with SSHClient(config) as client:
        # 使用管道处理数据
        commands = [
            "ps aux | grep python | wc -l",
            "df -h | grep -E '^/dev' | awk '{print $5}'",
            "netstat -tuln | grep :22 | wc -l",
            "ls -la /var/log | tail -5",
        ]
        
        for cmd in commands:
            result = client.exec_command(cmd)
            if result.exit_code == 0:
                print(f"✓ {cmd:50s} -> {result.stdout.strip()}")
            else:
                print(f"✗ {cmd:50s} -> 错误: {result.stderr[:50]}")


def example_3_file_operations():
    """示例3: 文件操作"""
    print("=" * 60)
    print("示例3: 文件操作")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-user",
        password="your-pass"
    )
    
    with SSHClient(config) as client:
        # 检查文件是否存在
        result = client.exec_command("test -f /etc/passwd && echo 'exists' || echo 'not found'")
        if "exists" in result.stdout:
            print("✓ /etc/passwd 存在")
        
        # 查看文件内容（前10行）
        result = client.exec_command("head -10 /etc/passwd")
        print(f"\n/etc/passwd 前10行:")
        print(result.stdout)
        
        # 检查磁盘空间
        result = client.exec_command("df -h / | tail -1 | awk '{print $4}'")
        print(f"根目录可用空间: {result.stdout.strip()}")


def example_4_service_management():
    """示例4: 服务管理"""
    print("=" * 60)
    print("示例4: 服务管理")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-user",
        password="your-pass"
    )
    
    service = "ssh"  # 或其他服务名
    
    with SSHClient(config) as client:
        # 检查服务状态
        result = client.exec_command(f"systemctl is-active {service}")
        status = "运行中" if result.exit_code == 0 else "已停止"
        print(f"服务 {service} 状态: {status}")
        
        # 查看服务日志（最近5行）
        result = client.exec_command(f"journalctl -u {service} --no-pager -n 5 2>/dev/null || tail -5 /var/log/syslog")
        print(f"\n最近日志:")
        print(result.stdout)


def example_5_backup_script():
    """示例5: 备份脚本"""
    print("=" * 60)
    print("示例5: 备份脚本")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-user",
        password="your-pass"
    )
    
    backup_dirs = ["/etc", "/var/log"]
    backup_dest = "/backup"
    
    with SSHClient(config) as client:
        # 创建备份目录
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = f"{backup_dest}/backup_{timestamp}"
        
        client.exec_command(f"mkdir -p {backup_path}")
        
        for src_dir in backup_dirs:
            print(f"备份 {src_dir}...")
            # 使用 tar 备份
            result = client.exec_command(
                f"tar czf {backup_path}/{src_dir.replace('/', '_')}.tar.gz {src_dir} 2>&1"
            )
            if result.exit_code == 0:
                print(f"  ✓ 成功")
            else:
                print(f"  ✗ 失败: {result.stderr[:100]}")
        
        # 列出备份文件
        result = client.exec_command(f"ls -lh {backup_path}")
        print(f"\n备份文件:")
        print(result.stdout)


def example_6_health_check():
    """示例6: 健康检查"""
    print("=" * 60)
    print("示例6: 健康检查")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-user",
        password="your-pass"
    )
    
    checks = {
        "CPU负载": "uptime | awk -F'load average:' '{print $2}'",
        "内存使用": "free | grep Mem | awk '{printf \"%.1f%\", $3/$2 * 100.0}'",
        "磁盘使用": "df -h / | tail -1 | awk '{print $5}'",
        "活动进程": "ps aux | wc -l",
        "登录用户": "who | wc -l",
        "网络连接": "netstat -tuln 2>/dev/null | grep LISTEN | wc -l || ss -tuln | grep LISTEN | wc -l",
    }
    
    with SSHClient(config) as client:
        print("\n系统健康检查:")
        print("-" * 40)
        
        for name, cmd in checks.items():
            result = client.exec_command(cmd)
            if result.exit_code == 0:
                value = result.stdout.strip()
                print(f"{name:12s}: {value}")
            else:
                print(f"{name:12s}: 无法获取")


def example_7_multi_server_task():
    """示例7: 多服务器任务"""
    print("=" * 60)
    print("示例7: 多服务器任务")
    print("=" * 60)
    
    # 服务器列表
    servers = [
        {"name": "Web-01", "host": "192.168.1.101", "user": "admin", "pass": "pass1"},
        {"name": "Web-02", "host": "192.168.1.102", "user": "admin", "pass": "pass2"},
    ]
    
    print("\n在所有服务器上执行更新...")
    
    for server in servers:
        config = SSHConfig(
            host=server["host"],
            username=server["user"],
            password=server["pass"]
        )
        
        print(f"\n[{server['name']}] {server['host']}")
        
        try:
            with SSHClient(config, use_pool=True) as client:
                # 更新包列表
                result = client.exec_command("sudo apt-get update -qq")
                if result.exit_code == 0:
                    print(f"  ✓ 包列表已更新")
                else:
                    print(f"  ✗ 更新失败: {result.stderr[:50]}")
                
                # 检查可升级包
                result = client.exec_command("apt list --upgradable 2>/dev/null | wc -l")
                count = result.stdout.strip()
                print(f"  → 可升级包: {count} 个")
                
        except Exception as e:
            print(f"  ✗ 连接失败: {e}")


def example_8_shell_interaction():
    """示例8: Shell交互"""
    print("=" * 60)
    print("示例8: Shell交互")
    print("=" * 60)
    
    config = SSHConfig(
        host="localhost",
        username="your-user",
        password="your-pass"
    )
    
    with SSHClient(config) as client:
        # 打开交互式Shell
        prompt = client.open_shell_session()
        print(f"检测到提示符: {prompt}\n")
        
        # 执行一系列相关命令
        commands = [
            ("cd /tmp", "切换到临时目录"),
            ("pwd", "查看当前目录"),
            ("touch test_file.txt", "创建测试文件"),
            ("ls -la test_file.txt", "验证文件创建"),
            ("rm test_file.txt", "删除测试文件"),
        ]
        
        for cmd, desc in commands:
            result = client.shell_command(cmd)
            print(f"[{desc}]")
            print(f"  $ {cmd}")
            if result.stdout.strip():
                print(f"  {result.stdout.strip()}")
            print()
        
        client.close_shell_session()


if __name__ == "__main__":
    print("高级模式示例\n")
    
    # 取消注释要运行的示例
    # example_1_connection_context_manager()
    # example_2_command_pipeline()
    # example_3_file_operations()
    # example_4_service_management()
    # example_5_backup_script()
    # example_6_health_check()
    # example_7_multi_server_task()
    # example_8_shell_interaction()
    
    print("\n示例完成！请根据实际需求修改配置。")
