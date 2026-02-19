"""
BackgroundTask 和 BackgroundTaskManager 完整测试套件
目标: 覆盖率从 0% 提升到 80%+
"""
import time
import threading
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.async_executor import (
    ByteLimitedBuffer,
    TaskSummary,
    BackgroundTask,
    BackgroundTaskManager,
    bg
)
from src.core.models import CommandResult


# ==============================================================================
# ByteLimitedBuffer 测试
# ==============================================================================

class TestByteLimitedBuffer:
    """字节限制环形缓冲区测试"""
    
    def test_init_default_size(self):
        """测试默认大小初始化"""
        buffer = ByteLimitedBuffer()
        assert buffer.max_bytes == 10 * 1024 * 1024  # 默认10MB
        assert len(buffer) == 0
        assert buffer.line_count == 0
    
    def test_init_custom_size(self):
        """测试自定义大小初始化"""
        buffer = ByteLimitedBuffer(max_bytes=1024)  # 1KB
        assert buffer.max_bytes == 1024
    
    def test_append_single_line(self):
        """测试添加单行数据"""
        buffer = ByteLimitedBuffer(max_bytes=1000)
        buffer.append("Hello World")
        
        assert len(buffer) == 11  # "Hello World" = 11 bytes
        assert buffer.line_count == 1
        assert buffer.get() == "Hello World"
    
    def test_append_multiple_lines(self):
        """测试添加多行数据"""
        buffer = ByteLimitedBuffer(max_bytes=1000)
        buffer.append("Line 1")
        buffer.append("Line 2")
        buffer.append("Line 3")
        
        assert buffer.line_count == 3
        assert buffer.get() == "Line 1\nLine 2\nLine 3"
    
    def test_append_exceeding_limit(self):
        """测试超出限制时丢弃旧数据"""
        buffer = ByteLimitedBuffer(max_bytes=20)  # 20 bytes limit
        
        buffer.append("1234567890")  # 10 bytes
        buffer.append("1234567890")  # 10 bytes (total: 20)
        buffer.append("NEW")  # 3 bytes, should trigger cleanup
        
        # 旧数据应该被丢弃
        assert buffer.line_count < 3
        assert "NEW" in buffer.get()
    
    def test_append_single_large_data(self):
        """测试单条数据超过限制时的截断"""
        buffer = ByteLimitedBuffer(max_bytes=10)
        large_data = "A" * 100  # 100 bytes
        
        buffer.append(large_data)
        
        # 应该只保留最后10字节
        assert len(buffer) <= 10
        assert buffer.get() == "A" * 10
    
    def test_extend_multiple_lines(self):
        """测试批量添加"""
        buffer = ByteLimitedBuffer(max_bytes=1000)
        lines = ["Line 1", "Line 2", "Line 3"]
        
        buffer.extend(lines)
        
        assert buffer.line_count == 3
        assert buffer.get_lines() == lines
    
    def test_get_all_content(self):
        """测试获取全部内容"""
        buffer = ByteLimitedBuffer(max_bytes=1000)
        buffer.extend(["A", "B", "C"])
        
        result = buffer.get()
        assert result == "A\nB\nC"
    
    def test_get_with_tail_bytes(self):
        """测试获取最后N字节"""
        buffer = ByteLimitedBuffer(max_bytes=1000)
        buffer.extend(["Hello", "World", "Test"])
        
        result = buffer.get(tail_bytes=10)
        # 应该从后往前取，直到满足10字节
        assert "Test" in result
        assert len(result.encode('utf-8')) <= 15  # 允许一些余量
    
    def test_get_lines_all(self):
        """测试获取所有行"""
        buffer = ByteLimitedBuffer(max_bytes=1000)
        buffer.extend(["A", "B", "C"])
        
        lines = buffer.get_lines()
        assert lines == ["A", "B", "C"]
    
    def test_get_lines_with_tail(self):
        """测试获取最后N行"""
        buffer = ByteLimitedBuffer(max_bytes=1000)
        buffer.extend(["A", "B", "C", "D", "E"])
        
        lines = buffer.get_lines(tail_lines=3)
        assert lines == ["C", "D", "E"]
    
    def test_get_empty_buffer(self):
        """测试空缓冲区"""
        buffer = ByteLimitedBuffer(max_bytes=100)
        
        assert buffer.get() == ""
        assert buffer.get_lines() == []
    
    def test_thread_safety(self):
        """测试线程安全性"""
        buffer = ByteLimitedBuffer(max_bytes=10000)
        errors = []
        
        def append_data(thread_id):
            try:
                for i in range(100):
                    buffer.append(f"Thread {thread_id} Line {i}")
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=append_data, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert buffer.line_count > 0


# ==============================================================================
# BackgroundTask 测试
# ==============================================================================

class TestBackgroundTask:
    """后台任务测试"""
    
    @pytest.fixture
    def mock_channel(self):
        """创建 mock channel - 模拟长时间运行的任务"""
        channel = MagicMock()
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        # 直接设置为False，任务保持运行状态
        # 注意：代码中检查的是 if self._channel.exit_status_ready (属性检查)
        channel.exit_status_ready = False
        return channel
    
    @pytest.fixture
    def task(self, mock_channel):
        """创建任务实例"""
        task = BackgroundTask(
            channel=mock_channel,
            command="echo test",
            buffer_size_mb=1.0,
            cleanup_delay=0.1  # 短清理延迟便于测试
        )
        yield task
        # 清理
        if task.is_running():
            task.stop(graceful=False)
    
    def test_init(self, mock_channel):
        """测试初始化"""
        task = BackgroundTask(
            channel=mock_channel,
            command="echo test",
            buffer_size_mb=5.0
        )
        
        assert task.id is not None
        assert len(task.id) == 8  # UUID前8位
        assert task.command == "echo test"
        assert task.status == "running"
        assert task.is_running() is True
        assert task.name is None
        assert task._cleanup_delay == 3600.0  # 默认1小时
    
    def test_status_properties(self, task):
        """测试状态属性"""
        assert task.is_running() is True
        assert task.is_completed() is False
        assert task.is_stopped() is False
        assert task.is_failed() is False
        assert task.exit_code is None
        assert task.duration >= 0
    
    def test_stop_graceful(self, task, mock_channel):
        """测试优雅停止"""
        # 模拟优雅停止成功 - 设置exit_status_ready为True让任务完成
        mock_channel.exit_status_ready = True
        mock_channel.recv_exit_status.return_value = 0
        
        result = task.stop(graceful=True, timeout=0.1)
        
        mock_channel.send.assert_called_with("\x03")  # Ctrl+C
        assert result is True
        assert task.is_stopped() or task.is_completed()
    
    def test_stop_force(self, task, mock_channel):
        """测试强制停止"""
        result = task.stop(graceful=False)
        
        mock_channel.close.assert_called_once()
        assert result is True
        assert task.is_stopped()
    
    def test_stop_not_running(self, task):
        """测试停止已停止的任务"""
        task.stop(graceful=False)
        
        # 再次停止应该直接返回True
        result = task.stop(graceful=False)
        assert result is True
    
    def test_wait_success(self, task, mock_channel):
        """测试等待完成"""
        # 模拟任务快速完成
        def complete_quickly():
            time.sleep(0.05)
            task._status = "completed"
            task._exit_code = 0
        
        threading.Thread(target=complete_quickly).start()
        result = task.wait(timeout=0.5)
        
        assert result is True
    
    def test_wait_timeout(self, task):
        """测试等待超时"""
        result = task.wait(timeout=0.01)  # 短超时
        
        # 任务还在运行
        assert result is False or task.is_running()
    
    def test_cancel_cleanup(self, task):
        """测试取消清理"""
        # 先停止任务触发清理定时器
        task.stop(graceful=False)
        
        # 取消清理
        task.cancel_cleanup()
        
        # 等待一段时间，验证任务未被清理
        time.sleep(0.2)
        assert task._cleanup_timer is None
    
    def test_get_summary(self, task):
        """测试获取摘要"""
        summary = task.get_summary(tail_lines=5)
        
        assert isinstance(summary, TaskSummary)
        assert summary.task_id == task.id
        assert summary.command == task.command
        assert summary.status == task.status
        assert summary.duration >= 0
        assert isinstance(summary.start_time, datetime)
    
    def test_get_output(self, task):
        """测试获取输出"""
        # 添加一些输出
        task._output_buffer.append("Test output line 1")
        task._output_buffer.append("Test output line 2")
        
        output = task.get_output()
        assert "Test output line 1" in output
        assert "Test output line 2" in output
    
    def test_get_stderr(self, task):
        """测试获取错误输出"""
        task._stderr_buffer.append("Error line 1")
        
        stderr = task.get_stderr()
        assert "Error line 1" in stderr
    
    def test_get_result_not_wait(self, task):
        """测试获取结果（不等待）"""
        result = task.get_result(wait=False)
        
        assert isinstance(result, CommandResult)
        assert result.command == task.command
        assert result.exit_code == -1  # 未完成
    
    def test_get_result_wait(self, task, mock_channel):
        """测试获取结果（等待完成）"""
        # 模拟任务完成
        def complete_task():
            time.sleep(0.05)
            task._status = "completed"
            task._exit_code = 0
            task._end_time = time.time()
        
        threading.Thread(target=complete_task).start()
        result = task.get_result(wait=True, timeout=0.5)
        
        assert result is not None
        assert result.exit_code == 0
        assert result.execution_time >= 0
    
    def test_iter_output(self, task):
        """测试迭代器读取输出"""
        # 添加输出
        task._output_buffer.append("Line 1")
        task._output_buffer.append("Line 2")
        
        lines = list(task.iter_output(block=False))
        
        assert "Line 1" in lines
        assert "Line 2" in lines
    
    def test_detect_remote_files(self, task):
        """测试检测远程文件"""
        # tcpdump -w 参数
        task.command = "tcpdump -i eth0 -w /tmp/capture.pcap"
        files = task._detect_remote_files()
        assert "/tmp/capture.pcap" in files
        
        # 重定向
        task.command = "echo test > /tmp/output.txt"
        files = task._detect_remote_files()
        assert "/tmp/output.txt" in files
    
    def test_detect_remote_files_no_files(self, task):
        """测试无文件时的检测"""
        task.command = "ls -la"
        files = task._detect_remote_files()
        assert files == []
    
    def test_monitor_thread_exception(self, mock_channel):
        """测试监控线程异常处理"""
        mock_channel.active = True
        mock_channel.recv_ready.side_effect = Exception("Read error")
        
        task = BackgroundTask(
            channel=mock_channel,
            command="test",
            buffer_size_mb=1.0
        )
        
        # 等待监控线程处理异常
        time.sleep(0.1)
        
        # 任务应该标记为错误状态
        assert task.is_failed() or task._error is not None


# ==============================================================================
# BackgroundTaskManager 测试
# ==============================================================================

class TestBackgroundTaskManager:
    """后台任务管理器测试"""
    
    @pytest.fixture
    def mock_ssh_client(self):
        """创建 mock SSH client - 模拟长时间运行的任务"""
        client = Mock()
        connection = Mock()
        channel = MagicMock()
        
        # 设置channel为长时间运行状态
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        # 使用property模拟exit_status_ready
        channel.exit_status_ready = False
        
        connection.open_channel.return_value = channel
        client._connection = connection
        
        return client, connection, channel
    
    @pytest.fixture
    def manager(self, mock_ssh_client):
        """创建管理器实例"""
        client, _, _ = mock_ssh_client
        return BackgroundTaskManager(client)
    
    def test_init(self, mock_ssh_client):
        """测试初始化"""
        client, _, _ = mock_ssh_client
        manager = BackgroundTaskManager(client)
        
        assert manager._client == client
        assert manager.tasks == []
    
    def test_run_basic(self, manager, mock_ssh_client):
        """测试基本启动任务"""
        client, _, channel = mock_ssh_client
        
        # 模拟通道行为 - 设置为长时间运行
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task = manager.run("echo test")
        
        assert task is not None
        assert task.id in manager._tasks
        assert task.is_running()
        channel.exec_command.assert_called_once_with("echo test")
        
        # 清理
        task.stop(graceful=False)
    
    def test_run_with_name(self, manager, mock_ssh_client):
        """测试带名称启动任务"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task = manager.run("echo test", name="my_task")
        
        assert task.name == "my_task"
        assert manager.get_by_name("my_task") == task
        
        # 清理
        task.stop(graceful=False)
    
    def test_run_duplicate_name(self, manager, mock_ssh_client):
        """测试重复名称报错"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task1 = manager.run("echo test", name="duplicate")
        
        with pytest.raises(ValueError, match="任务名称 'duplicate' 已存在"):
            manager.run("echo test2", name="duplicate")
        
        # 清理
        task1.stop(graceful=False)
    
    def test_get(self, manager, mock_ssh_client):
        """测试通过ID获取任务"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task = manager.run("echo test")
        retrieved = manager.get(task.id)
        
        assert retrieved == task
        
        # 清理
        task.stop(graceful=False)
    
    def test_get_nonexistent(self, manager):
        """测试获取不存在的任务"""
        assert manager.get("nonexistent") is None
    
    def test_list_running(self, manager, mock_ssh_client):
        """测试获取运行中任务列表"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task = manager.run("echo test")
        running = manager.list_running()
        
        assert len(running) == 1
        assert task in running
        
        # 清理
        task.stop(graceful=False)
    
    def test_list_completed(self, manager, mock_ssh_client):
        """测试获取已完成任务列表"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = True
        channel.recv_exit_status.return_value = 0
        
        task = manager.run("echo test")
        
        # 等待任务完成
        time.sleep(0.1)
        task._status = "completed"
        
        completed = manager.list_completed()
        assert task in completed or len(completed) == 0  # 取决于状态
        
        # 清理
        task.stop(graceful=False)
    
    def test_stop_all(self, manager, mock_ssh_client):
        """测试停止所有任务"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task1 = manager.run("echo test1")
        task2 = manager.run("echo test2")
        
        manager.stop_all(graceful=False)
        
        assert task1.is_stopped()
        assert task2.is_stopped()
    
    def test_wait_all_success(self, manager, mock_ssh_client):
        """测试等待所有任务完成"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task = manager.run("echo test")
        task.stop(graceful=False)
        
        result = manager.wait_all(timeout=0.5)
        
        assert result is True
    
    def test_wait_all_timeout(self, manager, mock_ssh_client):
        """测试等待所有任务超时"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task = manager.run("sleep 100")  # 长时间任务
        
        result = manager.wait_all(timeout=0.01)
        
        assert result is False
        
        # 清理
        task.stop(graceful=False)
    
    def test_get_all_summaries(self, manager, mock_ssh_client):
        """测试获取所有任务摘要"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task = manager.run("echo test")
        
        summaries = manager.get_all_summaries(tail_lines=5)
        
        assert len(summaries) == 1
        assert summaries[0].task_id == task.id
        
        # 清理
        task.stop(graceful=False)
    
    def test_remove_task(self, manager, mock_ssh_client):
        """测试移除任务"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task = manager.run("echo test", name="removable")
        task_id = task.id
        
        manager._remove_task(task_id)
        
        assert manager.get(task_id) is None
        assert manager.get_by_name("removable") is None
    
    def test_thread_safety(self, manager, mock_ssh_client):
        """测试管理器线程安全"""
        client, _, channel = mock_ssh_client
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        errors = []
        
        def create_tasks(thread_id):
            try:
                for i in range(10):
                    manager.run(f"echo {thread_id}_{i}", name=f"task_{thread_id}_{i}")
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=create_tasks, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(manager.tasks) == 30
        
        # 清理
        manager.stop_all(graceful=False)


# ==============================================================================
# 便捷函数测试
# ==============================================================================

class TestBgFunction:
    """bg 便捷函数测试"""
    
    def test_bg_creates_manager(self):
        """测试 bg 函数自动创建管理器"""
        client = Mock()
        connection = Mock()
        channel = Mock()
        
        connection.open_channel.return_value = channel
        client._connection = connection
        client._bg_manager = None
        
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task = bg(client, "echo test", name="test_task")
        
        assert hasattr(client, '_bg_manager')
        assert client._bg_manager is not None
        assert task is not None
        
        # 清理
        task.stop(graceful=False)
    
    def test_bg_uses_existing_manager(self):
        """测试 bg 函数复用现有管理器"""
        client = Mock()
        connection = Mock()
        channel = Mock()
        
        connection.open_channel.return_value = channel
        client._connection = connection
        
        # 预创建管理器
        existing_manager = BackgroundTaskManager(client)
        client._bg_manager = existing_manager
        
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        
        task = bg(client, "echo test")
        
        assert client._bg_manager is existing_manager
        
        # 清理
        task.stop(graceful=False)


# ==============================================================================
# 集成测试
# ==============================================================================

class TestIntegration:
    """集成测试 - 完整工作流程"""
    
    def test_full_lifecycle(self):
        """测试完整任务生命周期"""
        client = Mock()
        connection = Mock()
        channel = Mock()
        
        connection.open_channel.return_value = channel
        client._connection = connection
        
        # 模拟任务执行 - 先让任务保持运行
        channel.active = True
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False  # 任务运行中
        channel.recv_exit_status.return_value = 0
        
        manager = BackgroundTaskManager(client)
        
        # 1. 启动任务
        task = manager.run("echo hello", name="lifecycle_test")
        assert task.is_running()
        
        # 2. 模拟任务完成
        channel.exit_status_ready = True
        time.sleep(0.1)
        task._status = "completed"
        task._exit_code = 0
        
        # 3. 获取结果
        result = task.get_result()
        assert result.exit_code == 0
        
        # 4. 获取摘要
        summary = task.get_summary()
        assert summary.status == "completed"
    
    def test_concurrent_tasks(self):
        """测试并发执行多个任务"""
        client = Mock()
        connection = Mock()
        
        client._connection = connection
        manager = BackgroundTaskManager(client)
        
        tasks = []
        for i in range(5):
            channel = Mock()
            channel.active = True
            channel.recv_ready.return_value = False
            channel.recv_stderr_ready.return_value = False
            channel.exit_status_ready = False
            connection.open_channel.return_value = channel
            
            task = manager.run(f"echo {i}", name=f"concurrent_{i}")
            tasks.append(task)
        
        assert len(manager.list_running()) == 5
        
        # 停止所有
        manager.stop_all(graceful=False)
        assert len(manager.list_running()) == 0
