#!/usr/bin/env python3
"""
流式接收器等待时间优化对比测试

对比优化前后的等待时间和数据完整性
"""
import time
import sys
sys.path.insert(0, 'src')

from src import SSHClient, SSHConfig


def test_with_different_wait_times():
    """测试不同等待时间下的性能和完整性"""
    config = SSHConfig(
        host="aliyun.spiedeman.top",
        username="admin",
        password="bhr0204",
        timeout=30.0,
        command_timeout=60.0,
    )
    
    test_sizes = [
        (100000, "100KB"),
        (500000, "500KB"),
        (1048576, "1MB"),
    ]
    
    print("=" * 70)
    print("流式接收器性能测试")
    print("=" * 70)
    print(f"{'数据大小':<12} {'传输时间':<12} {'实际接收':<12} {'完整性':<10}")
    print("-" * 70)
    
    with SSHClient(config) as client:
        for size, label in test_sizes:
            total_received = 0
            start_time = time.time()
            
            def handle_chunk(stdout, stderr):
                nonlocal total_received
                if stdout:
                    total_received += len(stdout)
            
            result = client.exec_command_stream(
                f"yes X | head -c {size}",
                handle_chunk,
                timeout=60.0
            )
            
            elapsed = time.time() - start_time
            integrity = "OK" if total_received == size else f"FAIL {total_received}/{size}"
            
            print(f"{label:<12} {elapsed:<12.2f}s {total_received:<12,} {integrity:<10}")
    
    print("=" * 70)
    print("\n优化策略说明：")
    print("• 基于'数据静默期'的智能判断")
    print("• 收到退出码后，等待 100ms 无数据即认为完成")
    print("• 最大等待时间 1 秒（防止网络抖动）")
    print("• 渐进式检查间隔，减少 CPU 占用")


def compare_with_regular_exec():
    """对比流式 API 和普通 exec_command"""
    config = SSHConfig(
        host="aliyun.spiedeman.top",
        username="admin",
        password="bhr0204",
        timeout=30.0,
        command_timeout=60.0,
    )
    
    print("\n" + "=" * 70)
    print("流式 API vs 普通 exec_command 对比")
    print("=" * 70)
    
    with SSHClient(config) as client:
        # 普通 exec_command
        start = time.time()
        result1 = client.exec_command("yes Y | head -c 100000")
        regular_time = time.time() - start
        regular_size = len(result1.stdout)
        
        # 流式 exec_command_stream
        stream_size = 0
        start = time.time()
        
        def handle_chunk(stdout, stderr):
            nonlocal stream_size
            if stdout:
                stream_size += len(stdout)
        
        result2 = client.exec_command_stream(
            "yes Y | head -c 100000",
            handle_chunk,
            timeout=60.0
        )
        stream_time = time.time() - start
        
        print(f"\n普通 exec_command:")
        print(f"  耗时: {regular_time:.2f} 秒")
        print(f"  数据: {regular_size:,} bytes")
        print(f"  内存: O(n) - 累积所有输出")
        
        print(f"\n流式 exec_command_stream:")
        print(f"  耗时: {stream_time:.2f} 秒")
        print(f"  数据: {stream_size:,} bytes")
        print(f"  内存: O(1) - 实时处理")
        
        print(f"\n性能对比:")
        if stream_time < regular_time:
            print(f"  流式 API 快 {(regular_time/stream_time - 1)*100:.1f}%")
        else:
            print(f"  普通 API 快 {(stream_time/regular_time - 1)*100:.1f}%")
        
        print(f"\n完整性检查:")
        if regular_size == stream_size == 100000:
            print("  ✅ 两者都完整接收 100KB 数据")
        else:
            print(f"  ⚠️ 普通: {regular_size}, 流式: {stream_size}")


if __name__ == "__main__":
    try:
        test_with_different_wait_times()
        compare_with_regular_exec()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
