#!/usr/bin/env python3
"""
RemoteSSH - 高性能SSH客户端库演示

这是RemoteSSH库的演示脚本，展示了所有主要功能。
运行前请配置环境变量或修改代码中的连接信息。

运行方式:
    python main.py

环境变量配置:
    export REMOTE_SSH_HOST=your-host.com
    export REMOTE_SSH_USERNAME=your-username
    export REMOTE_SSH_PASSWORD=your-password
"""
import os
import time
import sys

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import SSHClient, SSHConfig, load_config
from src.pooling import get_pool_manager
from src.logging_config import configure_logging, get_logger
from src.exceptions import ConfigurationError, ConnectionError, CommandTimeoutError


# 配置日志
configure_logging(level="INFO", format="colored")
logger = get_logger(__name__)


def get_config():
    """获取SSH配置（从环境变量或代码）"""
    # 尝试从环境变量加载
    host = os.environ.get('REMOTE_SSH_HOST', 'localhost')
    username = os.environ.get('REMOTE_SSH_USERNAME', 'demo-user')
    password = os.environ.get('REMOTE_SSH_PASSWORD', 'demo-pass')
    
    if host == 'localhost' or host == 'your-host.com':
        print("⚠️  警告: 使用默认配置，请设置环境变量或修改代码")
        print("   export REMOTE_SSH_HOST=your-host.com")
        print("   export REMOTE_SSH_USERNAME=your-username")
        print("   export REMOTE_SSH_PASSWORD=your-password")
        print()
    
    return SSHConfig(
        host=host,
        username=username,
        password=password,
        timeout=10.0,
        command_timeout=30.0,
        recv_mode="auto"
    )


def example_1_basic_command():
    """示例1: 基本命令执行"""
    print("\n" + "="*60)
    print("示例1: 基本命令执行")
    print("="*60)
    
    config = get_config()
    
    try:
        with SSHClient(config) as client:
            # 执行系统命令
            commands = [
                ("whoami", "当前用户"),
                ("pwd", "当前目录"),
                ("uname -a", "系统信息"),
                ("date", "当前时间"),
            ]
            
            for cmd, desc in commands:
                result = client.exec_command(cmd)
                print(f"✓ {desc:12s}: {result.stdout.strip()}")
                
    except ConnectionError as e:
        print(f"✗ 连接失败: {e}")
    except Exception as e:
        print(f"✗ 错误: {e}")


def example_2_connection_pool():
    """示例2: 连接池性能对比"""
    print("\n" + "="*60)
    print("示例2: 连接池性能对比")
    print("="*60)
    
    config = get_config()
    num_commands = 5
    
    # 无连接池
    print("\n1. 无连接池模式:")
    start = time.time()
    for i in range(num_commands):
        with SSHClient(config, use_pool=False) as client:
            client.exec_command(f"echo 'No pool {i}'")
    no_pool_time = time.time() - start
    print(f"   执行{num_commands}次命令耗时: {no_pool_time:.2f}s")
    
    # 有连接池
    print("\n2. 连接池模式:")
    client = SSHClient(config, use_pool=True, max_size=3)
    start = time.time()
    for i in range(num_commands):
        client.exec_command(f"echo 'With pool {i}'")
    with_pool_time = time.time() - start
    client.disconnect()
    print(f"   执行{num_commands}次命令耗时: {with_pool_time:.2f}s")
    
    # 性能对比
    if with_pool_time > 0:
        speedup = no_pool_time / with_pool_time
        print(f"\n✓ 性能提升: {speedup:.1f}倍")


def example_3_shell_session():
    """示例3: Shell会话状态保持"""
    print("\n" + "="*60)
    print("示例3: Shell会话状态保持")
    print("="*60)
    
    config = get_config()
    
    try:
        with SSHClient(config) as client:
            # 打开Shell会话
            prompt = client.open_shell_session()
            print(f"✓ 检测到提示符: {prompt}")
            
            # 在Shell中执行命令（保持状态）
            print("\n在Shell中执行:")
            
            # 切换目录
            client.shell_command("cd /tmp")
            result = client.shell_command("pwd")
            print(f"  $ cd /tmp")
            print(f"  $ pwd")
            print(f"    当前目录: {result.stdout.strip()}")
            
            # 设置环境变量
            client.shell_command("export DEMO_VAR='HelloRemoteSSH'")
            result = client.shell_command("echo $DEMO_VAR")
            print(f"  $ export DEMO_VAR='HelloRemoteSSH'")
            print(f"  $ echo $DEMO_VAR")
            print(f"    环境变量: {result.stdout.strip()}")
            
            client.close_shell_session()
            print("\n✓ Shell会话已关闭")
            
    except Exception as e:
        print(f"✗ 错误: {e}")


def example_4_error_handling():
    """示例4: 错误处理"""
    print("\n" + "="*60)
    print("示例4: 错误处理")
    print("="*60)
    
    # 1. 配置错误
    print("\n1. 测试配置验证:")
    try:
        SSHConfig(host="", username="user", password="pass")
    except ConfigurationError as e:
        print(f"   ✓ 捕获配置错误: {e}")
    
    # 2. 无效端口
    try:
        SSHConfig(host="test.com", username="user", password="pass", port=70000)
    except ConfigurationError as e:
        print(f"   ✓ 捕获端口错误: {e}")
    
    # 3. 连接超时
    print("\n2. 测试连接超时:")
    config = SSHConfig(
        host=get_config().host,
        username=get_config().username,
        password=get_config().password,
        command_timeout=2.0
    )
    
    try:
        with SSHClient(config) as client:
            client.exec_command("sleep 10")
    except (CommandTimeoutError, TimeoutError) as e:
        print(f"   ✓ 捕获超时错误: {type(e).__name__}")
    except Exception as e:
        print(f"   ✗ 其他错误: {e}")


def example_5_parallel_creation():
    """示例5: 并行创建连接"""
    print("\n" + "="*60)
    print("示例5: 并行创建连接")
    print("="*60)
    
    config = get_config()
    
    print("\n1. 串行创建5个连接:")
    start = time.time()
    client_serial = SSHClient(config, use_pool=True, max_size=5, min_size=5, parallel_init=False)
    serial_time = time.time() - start
    stats = client_serial._pool.stats
    print(f"   创建{stats['created']}个连接耗时: {serial_time:.3f}s")
    client_serial.disconnect()
    
    print("\n2. 并行创建5个连接:")
    start = time.time()
    client_parallel = SSHClient(config, use_pool=True, max_size=5, min_size=5, parallel_init=True)
    parallel_time = time.time() - start
    stats = client_parallel._pool.stats
    print(f"   创建{stats['created']}个连接耗时: {parallel_time:.3f}s")
    client_parallel.disconnect()
    
    if parallel_time > 0:
        speedup = serial_time / parallel_time
        print(f"\n✓ 并行创建速度提升: {speedup:.1f}倍")


def example_6_config_management():
    """示例6: 配置管理"""
    print("\n" + "="*60)
    print("示例6: 配置管理")
    print("="*60)
    
    print("\n1. 从代码创建配置:")
    config1 = SSHConfig(
        host="server1.example.com",
        username="admin",
        password="secret",
        port=2222
    )
    print(f"   ✓ {config1}")
    
    print("\n2. 配置复制和修改:")
    config2 = config1.copy_with(port=22, timeout=60.0)
    print(f"   原端口: {config1.port}, 新端口: {config2.port}")
    print(f"   原超时: {config1.timeout}s, 新超时: {config2.timeout}s")
    
    print("\n3. 配置导出为字典:")
    config_dict = config1.to_dict()
    print(f"   Host: {config_dict['host']}")
    print(f"   Port: {config_dict['port']}")


def run_all_examples():
    """运行所有示例"""
    examples = [
        ("基本命令执行", example_1_basic_command),
        ("连接池性能对比", example_2_connection_pool),
        ("Shell会话状态保持", example_3_shell_session),
        ("错误处理", example_4_error_handling),
        ("并行创建连接", example_5_parallel_creation),
        ("配置管理", example_6_config_management),
    ]
    
    print("\n" + "="*60)
    print("RemoteSSH 演示脚本")
    print("="*60)
    print("\n注意: 请确保已设置SSH连接信息")
    
    # 询问是否继续
    response = input("\n是否运行所有示例? (y/n): ").lower()
    if response != 'y':
        print("取消运行")
        return
    
    print("\n" + "="*60)
    print("开始运行示例...")
    print("="*60)
    
    for name, func in examples:
        try:
            func()
        except KeyboardInterrupt:
            print("\n\n用户中断")
            break
        except Exception as e:
            print(f"\n✗ 示例 '{name}' 失败: {e}")
    
    print("\n" + "="*60)
    print("示例运行完成!")
    print("="*60)
    print("\n更多示例请参见 examples/ 目录")


if __name__ == "__main__":
    try:
        run_all_examples()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n程序错误: {e}")
        sys.exit(1)
