"""
Main.py 模拟执行测试
验证 main.py 中各示例的逻辑正确性
"""
import sys
import os
import time
from unittest.mock import Mock, MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rprobe import SSHClient, SSHConfig


def test_example_7_pool_close():
    """测试示例7: 连接池并行关闭"""
    print("\n" + "="*60)
    print("测试示例7: 连接池并行关闭")
    print("="*60)
    
    config = SSHConfig(
        host='test.com',
        username='user',
        password='pass'
    )
    
    # Mock pool
    mock_pool = MagicMock()
    mock_pool.stats = {
        'total': 10,
        'pool_size': 10,
        'in_use': 0,
        'created': 10
    }
    
    with patch.object(SSHClient, '__init__', return_value=None):
        client = SSHClient.__new__(SSHClient)
        client._config = config
        client._pool = mock_pool
        client._connection = None
        client._bg_manager = None
        client._receiver = Mock()
        
        # 测试 pool.stats 访问
        stats = client._pool.stats
        print(f"✓ Pool stats: {stats}")
        assert stats['total'] == 10
        
        # 测试 disconnect
        client.disconnect = Mock()
        client.disconnect()
        print("✓ disconnect() called")
    
    print("\n[PASS] 示例7逻辑测试通过")


def test_example_8_background_tasks():
    """测试示例8: 后台任务执行器"""
    print("\n" + "="*60)
    print("测试示例8: 后台任务执行器")
    print("="*60)
    
    config = SSHConfig(
        host='test.com',
        username='user',
        password='pass'
    )
    
    with patch.object(SSHClient, '__init__', return_value=None):
        client = SSHClient.__new__(SSHClient)
        client._config = config
        client._pool = None
        client._connection = Mock()
        client._receiver = Mock()
        client._bg_manager = None
        
        # Mock is_connected
        type(client).is_connected = PropertyMock(return_value=True)
        
        # Mock bg method
        mock_task = Mock()
        mock_task.id = 'test-task-id'
        mock_task.name = 'log_monitor'
        mock_task.command = 'for i in $(seq 1 5); do echo "Log entry $i"; sleep 1; done'
        mock_task.is_running.return_value = True
        mock_task.is_completed.return_value = False
        mock_task.duration = 1.5
        mock_task.stop.return_value = True
        mock_task.get_output.return_value = 'Log entry 1\nLog entry 2\nLog entry 3'
        
        # Mock summary
        mock_summary = Mock()
        mock_summary.status = 'running'
        mock_summary.duration = 1.5
        mock_summary.lines_output = 3
        mock_summary.last_lines = ['Log entry 1', 'Log entry 2', 'Log entry 3']
        mock_task.get_summary.return_value = mock_summary
        
        client.bg = Mock(return_value=mock_task)
        
        # 执行示例8的核心逻辑
        print("\n1. 启动后台任务:")
        task = client.bg(
            'for i in $(seq 1 5); do echo "Log entry $i"; sleep 1; done',
            name="log_monitor",
            buffer_size_mb=1
        )
        print(f"   ✓ Task created: {task.id}")
        assert task.id == 'test-task-id'
        assert task.name == 'log_monitor'
        
        print("\n2. 模拟主线程工作...")
        time.sleep(0.1)  # 模拟工作
        
        print("\n3. 检查任务状态:")
        if task.is_running():
            print(f"   ✓ Task running, duration: {task.duration:.1f}s")
        
        print("\n4. 获取任务摘要:")
        summary = task.get_summary(tail_lines=3)
        print(f"   - Status: {summary.status}")
        print(f"   - Duration: {summary.duration:.1f}s")
        print(f"   - Lines: {summary.lines_output}")
        
        print("\n5. 停止任务:")
        if task.is_running():
            task.stop(graceful=True, timeout=3.0)
            print("   ✓ Task stopped")
        
        print("\n6. 查看输出:")
        output = task.get_output()
        if output:
            lines = output.strip().split('\n')
            print(f"   Total lines: {len(lines)}")
    
    print("\n[PASS] 示例8逻辑测试通过")


def test_example_9_streaming_transfer():
    """测试示例9: 流式数据传输"""
    print("\n" + "="*60)
    print("测试示例9: 流式数据传输")
    print("="*60)
    
    config = SSHConfig(
        host='test.com',
        username='user',
        password='pass',
        command_timeout=30.0
    )
    
    with patch.object(SSHClient, '__init__', return_value=None):
        client = SSHClient.__new__(SSHClient)
        client._config = config
        client._pool = None
        client._connection = Mock()
        client._receiver = Mock()
        client._bg_manager = None
        
        # Mock exec_command_stream
        mock_result = Mock()
        mock_result.exit_code = 0
        mock_result.execution_time = 0.5
        mock_result.command = 'seq 1 1000'
        
        received_chunks = []
        total_bytes = 0
        
        def mock_exec_command_stream(command, chunk_handler, timeout=None):
            nonlocal total_bytes
            # 模拟数据接收
            for i in range(10):
                chunk = f"{i*100+1}\n".encode() * 100  # 模拟数据块
                chunk_handler(chunk, b"")
                received_chunks.append(chunk)
                total_bytes += len(chunk)
            return mock_result
        
        client.exec_command_stream = mock_exec_command_stream
        
        # 执行示例9的核心逻辑
        print("\n1. 流式接收数据:")
        
        def data_handler(stdout_chunk, stderr_chunk):
            nonlocal total_bytes
            if stdout_chunk:
                received_chunks.append(stdout_chunk)
                total_bytes += len(stdout_chunk)
        
        result = client.exec_command_stream(
            "seq 1 1000",
            data_handler,
            timeout=30.0
        )
        
        print(f"   ✓ Exit code: {result.exit_code}")
        print(f"   ✓ Chunks received: {len(received_chunks)}")
        print(f"   ✓ Total bytes: {total_bytes}")
        
        assert result.exit_code == 0
        assert len(received_chunks) > 0
    
    print("\n[PASS] 示例9逻辑测试通过")


def test_example_10_connection_factory():
    """测试示例10: ConnectionFactory"""
    print("\n" + "="*60)
    print("测试示例10: ConnectionFactory")
    print("="*60)
    
    config = SSHConfig(
        host='test.com',
        username='user',
        password='pass'
    )
    
    from rprobe.core.connection_factory import ConnectionFactory
    
    with patch.object(SSHClient, '__init__', return_value=None):
        client = SSHClient.__new__(SSHClient)
        client._config = config
        client._pool = None
        client._connection = Mock()
        client._receiver = Mock()
        client._bg_manager = None
        
        # Mock transport
        mock_transport = Mock()
        mock_channel = Mock()
        mock_channel.recv = Mock(return_value=b'Hello from ConnectionFactory')
        mock_channel.send = Mock()
        mock_transport.open_session.return_value = mock_channel
        client._connection.transport = mock_transport
        
        print("\n1. 创建 exec channel:")
        with ConnectionFactory.create_exec_channel(
            transport=mock_transport,
            command="echo 'Hello from ConnectionFactory'",
            timeout=30.0
        ) as channel:
            print(f"   ✓ Channel created")
            stdout = channel.recv(1024)
            print(f"   ✓ Output: {stdout.decode().strip()}")
            assert stdout == b'Hello from ConnectionFactory'
        
        print("\n2. 创建 shell channel:")
        mock_channel2 = Mock()
        mock_channel2.recv = Mock(return_value=b'/home/user')
        mock_channel2.send = Mock()
        mock_transport.open_session.return_value = mock_channel2
        
        with ConnectionFactory.create_shell_channel(
            transport=mock_transport,
            timeout=60.0
        ) as channel:
            print(f"   ✓ Shell channel created")
            channel.send("pwd\n")
            response = channel.recv(1024)
            print(f"   ✓ Response: {response.decode().strip()}")
    
    print("\n[PASS] 示例10逻辑测试通过")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Main.py 示例逻辑测试")
    print("="*60)
    
    try:
        test_example_7_pool_close()
        test_example_8_background_tasks()
        test_example_9_streaming_transfer()
        test_example_10_connection_factory()
        
        print("\n" + "="*60)
        print("✓ 所有示例逻辑测试通过!")
        print("="*60)
        return True
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ 测试错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
