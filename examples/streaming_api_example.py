"""
流式 API 使用示例

展示如何使用 exec_command_stream 进行超大数据传输
"""
import io
import sys
from src import SSHClient, SSHConfig


def example_basic_streaming():
    """基本流式传输示例"""
    config = SSHConfig(
        host="your-host",
        username="your-user",
        password="your-pass"
    )
    
    with SSHClient(config) as client:
        total_size = 0
        
        def handle_chunk(stdout, stderr):
            nonlocal total_size
            if stdout:
                total_size += len(stdout)
                print(f"收到 {len(stdout)} 字节数据")
        
        # 传输 10MB 数据
        result = client.exec_command_stream(
            "cat /var/log/large.log",
            handle_chunk,
            timeout=300.0
        )
        
        print(f"传输完成，总共接收: {total_size} 字节")
        print(f"退出码: {result.exit_code}")


def example_write_to_file():
    """将流式数据写入文件"""
    config = SSHConfig(
        host="your-host",
        username="your-user",
        password="your-pass"
    )
    
    with SSHClient(config) as client:
        with open("output.log", "wb") as f:
            def handle_chunk(stdout, stderr):
                if stdout:
                    f.write(stdout)
                if stderr:
                    sys.stderr.buffer.write(stderr)
            
            result = client.exec_command_stream(
                "tar czf - /var/data",
                handle_chunk,
                timeout=600.0
            )
            
            print(f"文件传输完成，退出码: {result.exit_code}")


def example_process_in_realtime():
    """实时处理数据（例如日志分析）"""
    config = SSHConfig(
        host="your-host",
        username="your-user",
        password="your-pass"
    )
    
    with SSHClient(config) as client:
        error_count = 0
        line_buffer = b""
        
        def handle_chunk(stdout, stderr):
            nonlocal error_count, line_buffer
            
            if stdout:
                # 累积到缓冲区
                line_buffer += stdout
                
                # 按行处理
                while b"\n" in line_buffer:
                    line, line_buffer = line_buffer.split(b"\n", 1)
                    line_str = line.decode("utf-8", errors="replace")
                    
                    # 实时分析日志
                    if "ERROR" in line_str:
                        error_count += 1
                        print(f"发现错误: {line_str}")
            
            if stderr:
                sys.stderr.buffer.write(stderr)
        
        result = client.exec_command_stream(
            "tail -f /var/log/app.log",
            handle_chunk,
            timeout=60.0
        )
        
        print(f"分析完成，共发现 {error_count} 个错误")


def example_progress_tracking():
    """进度追踪示例"""
    import time
    
    config = SSHConfig(
        host="your-host",
        username="your-user",
        password="your-pass"
    )
    
    with SSHClient(config) as client:
        total_received = 0
        last_update = time.time()
        expected_size = 100 * 1024 * 1024  # 100MB
        
        def handle_chunk(stdout, stderr):
            nonlocal total_received, last_update
            
            if stdout:
                total_received += len(stdout)
                
                # 每秒更新一次进度
                current_time = time.time()
                if current_time - last_update >= 1.0:
                    progress = (total_received / expected_size) * 100
                    print(f"进度: {progress:.1f}% ({total_received / 1024 / 1024:.1f} MB)")
                    last_update = current_time
        
        result = client.exec_command_stream(
            "dd if=/dev/zero bs=1M count=100",
            handle_chunk,
            timeout=300.0
        )
        
        print(f"传输完成: {total_received / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    print("流式 API 使用示例")
    print("=" * 60)
    print()
    print("可用示例:")
    print("1. example_basic_streaming() - 基本流式传输")
    print("2. example_write_to_file() - 写入文件")
    print("3. example_process_in_realtime() - 实时处理")
    print("4. example_progress_tracking() - 进度追踪")
    print()
    print("修改配置后取消注释相应函数调用")
    print("=" * 60)
