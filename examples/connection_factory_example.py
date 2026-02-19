"""
ConnectionFactory 使用示例

演示如何使用 ConnectionFactory 统一创建和管理 SSH Channel
"""
from src import SSHClient, SSHConfig
from src.core.connection_factory import ConnectionFactory


def example_basic_usage():
    """基本使用示例 - 直接创建 channel"""
    config = SSHConfig(
        host="your-server.com",
        username="root",
        password="your-password"
    )
    
    client = SSHClient(config)
    client.connect()
    
    try:
        transport = client._connection.transport
        
        # 使用 ConnectionFactory 创建 exec channel
        with ConnectionFactory.create_exec_channel(
            transport=transport,
            command="ls -la",
            timeout=30.0
        ) as channel:
            # channel 已配置好，可以直接使用
            stdout = channel.recv(1024)
            print(f"输出: {stdout.decode()}")
        
        # channel 自动关闭
        
        # 创建 shell channel
        with ConnectionFactory.create_shell_channel(
            transport=transport,
            timeout=60.0
        ) as channel:
            # 使用交互式 shell
            channel.send("pwd\n")
            time.sleep(0.5)
            output = channel.recv(1024)
            print(f"Shell 输出: {output.decode()}")
    
    finally:
        client.disconnect()


def example_with_connection_manager():
    """使用 ConnectionManager 创建 channel"""
    config = SSHConfig(
        host="your-server.com",
        username="root",
        password="your-password"
    )
    
    client = SSHClient(config)
    client.connect()
    
    try:
        # 使用 ConnectionManager 作为连接源
        with ConnectionFactory.create_exec_channel(
            connection_source=client._connection,
            use_pool=False,  # 直接连接模式
            command="cat /etc/os-release",
            timeout=10.0
        ) as channel:
            stdout = b""
            while True:
                data = channel.recv(4096)
                if not data:
                    break
                stdout += data
            print(stdout.decode())
    
    finally:
        client.disconnect()


def example_simple_channel():
    """简单 channel 创建（非上下文管理器）"""
    config = SSHConfig(
        host="your-server.com",
        username="root",
        password="your-password"
    )
    
    client = SSHClient(config)
    client.connect()
    
    try:
        transport = client._connection.transport
        
        # 简单创建 channel（需要自己管理生命周期）
        channel = ConnectionFactory.create_channel_simple(
            transport=transport,
            channel_type="exec",
            command="echo 'Hello World'",
            timeout=10.0
        )
        
        try:
            stdout = channel.recv(1024)
            print(f"输出: {stdout.decode()}")
        finally:
            # 手动关闭
            channel.close()
    
    finally:
        client.disconnect()


def example_error_handling():
    """错误处理示例"""
    config = SSHConfig(
        host="your-server.com",
        username="root",
        password="your-password"
    )
    
    client = SSHClient(config)
    client.connect()
    
    try:
        transport = client._connection.transport
        
        # 即使发生异常，channel 也会自动关闭
        try:
            with ConnectionFactory.create_exec_channel(
                transport=transport,
                command="exit 1",  # 命令返回错误码
                timeout=10.0
            ) as channel:
                stdout = channel.recv(1024)
                exit_code = channel.recv_exit_status()
                print(f"退出码: {exit_code}")
                
                # 模拟处理错误
                raise RuntimeError("处理失败")
        except RuntimeError as e:
            print(f"捕获异常: {e}")
            # channel 已自动关闭
    
    finally:
        client.disconnect()


def example_comparison():
    """对比: 使用 ConnectionFactory vs 手动创建"""
    
    print("=== 手动创建（代码重复，易出错）===")
    """
    # 重复代码多
    channel = transport.open_session()
    try:
        channel.settimeout(30.0)
        channel.exec_command("ls -la")
        # 使用 channel...
    finally:
        try:
            channel.close()
        except:
            pass
    """
    
    print("\n=== 使用 ConnectionFactory（简洁，自动管理）===")
    """
    # 一行代码，自动管理生命周期
    with ConnectionFactory.create_exec_channel(
        transport=transport,
        command="ls -la",
        timeout=30.0
    ) as channel:
        # 使用 channel...
        pass  # 自动关闭
    """


if __name__ == "__main__":
    import time
    
    print("ConnectionFactory 使用示例")
    print("=" * 50)
    print("\n请根据实际环境修改配置后运行示例")
    print("\n示例功能:")
    print("1. example_basic_usage() - 基本使用")
    print("2. example_with_connection_manager() - 使用 ConnectionManager")
    print("3. example_simple_channel() - 简单 channel 创建")
    print("4. example_error_handling() - 错误处理")
    print("5. example_comparison() - 对比示例")
