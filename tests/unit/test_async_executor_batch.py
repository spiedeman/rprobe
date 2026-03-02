"""
BatchTaskResult 和 run_batch 批量任务功能测试
"""

import time
import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import List

from rprobe.core.async_executor import (
    BackgroundTaskManager,
    BackgroundTask,
    BatchTaskResult,
    TaskStatus,
    TaskSummary,
)


class TestBatchTaskResult:
    """测试 BatchTaskResult 类"""

    @pytest.fixture
    def mock_manager(self):
        """创建 Mock BackgroundTaskManager"""
        manager = Mock(spec=BackgroundTaskManager)
        manager.list_running = Mock(return_value=[])
        manager.list_completed = Mock(return_value=[])
        manager.wait_all = Mock(return_value=True)
        manager.stop_all = Mock()
        manager.get_all_summaries = Mock(return_value=[])
        return manager

    @pytest.fixture
    def mock_tasks(self):
        """创建 Mock BackgroundTask 列表"""
        tasks = []
        for i in range(3):
            task = Mock(spec=BackgroundTask)
            task.id = f"task_{i}"
            task.name = f"task_name_{i}"
            tasks.append(task)
        return tasks

    def test_batch_result_initialization(self, mock_manager, mock_tasks):
        """测试 BatchTaskResult 初始化"""
        batch = BatchTaskResult(tasks=mock_tasks, manager=mock_manager)
        
        assert batch.tasks == mock_tasks
        assert batch.manager == mock_manager

    def test_wait_all_delegates_to_manager(self, mock_manager, mock_tasks):
        """测试 wait_all 委托给 manager"""
        batch = BatchTaskResult(tasks=mock_tasks, manager=mock_manager)
        
        result = batch.wait_all(timeout=100)
        
        mock_manager.wait_all.assert_called_once_with(100)
        assert result is True

    def test_stop_all_delegates_to_manager(self, mock_manager, mock_tasks):
        """测试 stop_all 委托给 manager"""
        batch = BatchTaskResult(tasks=mock_tasks, manager=mock_manager)
        
        batch.stop_all(graceful=False, timeout=10.0)
        
        mock_manager.stop_all.assert_called_once_with(False, 10.0)

    def test_get_summaries_delegates_to_manager(self, mock_manager, mock_tasks):
        """测试 get_summaries 委托给 manager"""
        mock_summaries = [Mock(spec=TaskSummary) for _ in range(3)]
        mock_manager.get_all_summaries.return_value = mock_summaries
        
        batch = BatchTaskResult(tasks=mock_tasks, manager=mock_manager)
        result = batch.get_summaries(tail_lines=20)
        
        mock_manager.get_all_summaries.assert_called_once_with(20)
        assert result == mock_summaries

    def test_running_count_property(self, mock_manager, mock_tasks):
        """测试 running_count 属性"""
        mock_manager.list_running.return_value = [Mock(), Mock()]  # 2个运行中
        
        batch = BatchTaskResult(tasks=mock_tasks, manager=mock_manager)
        
        assert batch.running_count == 2
        mock_manager.list_running.assert_called()

    def test_completed_count_property(self, mock_manager, mock_tasks):
        """测试 completed_count 属性"""
        mock_manager.list_completed.return_value = [Mock()]  # 1个已完成
        
        batch = BatchTaskResult(tasks=mock_tasks, manager=mock_manager)
        
        assert batch.completed_count == 1
        mock_manager.list_completed.assert_called()

    def test_all_completed_property_true(self, mock_manager, mock_tasks):
        """测试 all_completed 属性 - 所有任务完成"""
        mock_manager.list_running.return_value = []  # 没有运行中的
        
        batch = BatchTaskResult(tasks=mock_tasks, manager=mock_manager)
        
        assert batch.all_completed is True

    def test_all_completed_property_false(self, mock_manager, mock_tasks):
        """测试 all_completed 属性 - 还有任务在运行"""
        mock_manager.list_running.return_value = [Mock()]  # 还有运行中的
        
        batch = BatchTaskResult(tasks=mock_tasks, manager=mock_manager)
        
        assert batch.all_completed is False


class TestBackgroundTaskManagerRunBatch:
    """测试 BackgroundTaskManager.run_batch 方法"""

    @pytest.fixture
    def mock_client(self):
        """创建 Mock SSHClient"""
        client = Mock()
        client._use_pool = False
        client._connection = Mock()
        client._connection.transport = Mock()
        return client

    @pytest.fixture
    def mock_manager(self, mock_client):
        """创建 BackgroundTaskManager，mock掉 run 方法"""
        manager = BackgroundTaskManager(mock_client)
        
        # Mock _create_shell_channel 避免真实SSH操作
        manager._create_shell_channel = Mock(return_value=Mock())
        
        # Mock run 方法返回 Mock Task
        manager.run = Mock()
        mock_tasks = []
        for i in range(3):
            mock_task = Mock(spec=BackgroundTask)
            mock_task.id = f"batch_task_{i}"
            mock_task.name = f"task_{i}"
            mock_task.is_running = Mock(return_value=True)
            mock_tasks.append(mock_task)
        
        # 每次调用返回不同的task
        manager.run.side_effect = mock_tasks
        
        return manager, mock_tasks

    def test_run_batch_basic(self, mock_manager):
        """测试基本的 run_batch 功能"""
        manager, _ = mock_manager
        
        commands = [
            {"command": "echo 1", "name": "task1"},
            {"command": "echo 2", "name": "task2"},
            {"command": "echo 3", "name": "task3"},
        ]
        
        batch = manager.run_batch(commands)
        
        assert isinstance(batch, BatchTaskResult)
        assert len(batch.tasks) == 3
        assert manager.run.call_count == 3

    def test_run_batch_with_custom_params(self, mock_manager):
        """测试 run_batch 传递自定义参数"""
        manager, _ = mock_manager
        
        commands = [
            {"command": "echo 1", "name": "task1", "buffer_size_mb": 5.0, "cleanup_delay": 1800.0},
            {"command": "echo 2", "name": "task2", "buffer_size_mb": 20.0},
        ]
        
        batch = manager.run_batch(commands)
        
        # 验证参数传递
        first_call = manager.run.call_args_list[0]
        assert first_call.kwargs["buffer_size_mb"] == 5.0
        assert first_call.kwargs["cleanup_delay"] == 1800.0
        
        second_call = manager.run.call_args_list[1]
        assert second_call.kwargs["buffer_size_mb"] == 20.0
        assert second_call.kwargs["cleanup_delay"] == 3600.0  # 默认值

    def test_run_batch_concurrent_control(self, mock_manager):
        """测试批量任务启动 - 立即启动所有任务，不阻塞"""
        manager, _ = mock_manager

        # 模拟当前有2个任务在运行
        manager._tasks = {"existing1": Mock(is_running=lambda: True), "existing2": Mock(is_running=lambda: True)}

        commands = [
            {"command": "echo 1", "name": "task1"},
            {"command": "echo 2", "name": "task2"},
        ]

        # run_batch 现在立即启动所有任务，不等待槽位
        batch = manager.run_batch(commands, max_concurrent=3)

        # 所有任务都应该被启动
        assert manager.run.call_count == 2

    def test_run_batch_delay_between_tasks(self, mock_manager):
        """测试任务间延迟"""
        manager, _ = mock_manager
        
        commands = [
            {"command": "echo 1", "name": "task1"},
            {"command": "echo 2", "name": "task2"},
        ]
        
        with patch('time.sleep') as mock_sleep:
            batch = manager.run_batch(commands, batch_delay=0.5)
            
            # 2个任务，中间应该有1次延迟（最后一个任务后不需要延迟）
            mock_sleep.assert_called_with(0.5)
            assert mock_sleep.call_count == 1

    def test_run_batch_empty_commands(self, mock_manager):
        """测试空任务列表"""
        manager, _ = mock_manager
        
        batch = manager.run_batch([])
        
        assert isinstance(batch, BatchTaskResult)
        assert len(batch.tasks) == 0
        manager.run.assert_not_called()

    def test_run_batch_single_command(self, mock_manager):
        """测试单个任务"""
        manager, _ = mock_manager
        
        commands = [{"command": "echo test", "name": "single"}]
        
        batch = manager.run_batch(commands)
        
        assert len(batch.tasks) == 1
        manager.run.assert_called_once()


class TestBatchTaskIntegration:
    """批量任务集成测试 - 模拟真实使用场景"""

    def test_batch_workflow(self):
        """测试完整的批量任务工作流"""
        # 创建 Mock
        mock_client = Mock()
        mock_client._use_pool = False
        mock_client._connection = Mock()
        
        manager = BackgroundTaskManager(mock_client)
        manager._create_shell_channel = Mock(return_value=Mock())
        
        # Mock run 方法返回带状态的 task
        mock_tasks = []
        for i in range(3):
            task = Mock(spec=BackgroundTask)
            task.id = f"task_{i}"
            task.name = f"name_{i}"
            task.status = TaskStatus.RUNNING if i < 2 else TaskStatus.COMPLETED
            # 使用 side_effect 来模拟状态变化
            call_count = [0]
            def make_is_running(running):
                def is_running():
                    call_count[0] += 1
                    return running
                return is_running
            task.is_running = Mock(side_effect=make_is_running(i < 2))
            mock_tasks.append(task)
        
        manager.run = Mock(side_effect=mock_tasks)
        
        # 直接 Mock manager 的方法
        manager.list_running = Mock(return_value=[mock_tasks[0], mock_tasks[1]])
        manager.list_completed = Mock(return_value=[mock_tasks[2]])
        
        # 执行批量任务
        commands = [{"command": f"cmd{i}", "name": f"name_{i}"} for i in range(3)]
        batch = manager.run_batch(commands)
        
        # 验证工作流
        assert len(batch.tasks) == 3
        
        # 检查初始状态（2个运行中，1个完成）
        assert batch.running_count == 2
        assert batch.completed_count == 1
        assert batch.all_completed is False
        
        # 模拟所有任务完成
        manager.list_running = Mock(return_value=[])
        manager.list_completed = Mock(return_value=mock_tasks)
        
        # 再次检查
        assert batch.running_count == 0
        assert batch.completed_count == 3
        assert batch.all_completed is True

    def test_batch_error_handling(self):
        """测试批量任务错误处理"""
        mock_client = Mock()
        mock_client._use_pool = False
        mock_client._connection = Mock()
        
        manager = BackgroundTaskManager(mock_client)
        manager._create_shell_channel = Mock(return_value=Mock())
        
        # 模拟第2个任务失败
        def side_effect(*args, **kwargs):
            if kwargs.get("name") == "task2":
                raise RuntimeError("Task failed")
            task = Mock(spec=BackgroundTask)
            task.id = kwargs.get("name", "default")
            return task
        
        manager.run = Mock(side_effect=side_effect)
        
        commands = [
            {"command": "echo 1", "name": "task1"},
            {"command": "echo 2", "name": "task2"},  # 会失败
            {"command": "echo 3", "name": "task3"},
        ]
        
        # 应该抛出异常
        with pytest.raises(RuntimeError, match="Task failed"):
            manager.run_batch(commands)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
