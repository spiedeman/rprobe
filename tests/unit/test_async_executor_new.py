"""
后台任务状态机和强制Shell模式测试
新增测试用例覆盖修复的5个问题
"""

import time
import threading
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from rprobe.core.async_executor import (
    ByteLimitedBuffer,
    BackgroundTask,
    BackgroundTaskManager,
    bg,
    TaskSummary,
)
from rprobe.core.task_status import (
    TaskStatus,
    TaskStateMachine,
    StatusChangeEvent,
)
from rprobe.core.models import CommandResult


# ==============================================================================
# TaskStatus 枚举测试
# ==============================================================================

class TestTaskStatus:
    """任务状态枚举测试"""

    def test_status_values(self):
        """测试状态值"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.STOPPING.value == "stopping"
        assert TaskStatus.STOPPED.value == "stopped"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.ERROR.value == "error"
        assert TaskStatus.TIMEOUT.value == "timeout"

    def test_is_terminal(self):
        """测试终态判断"""
        # 终态
        assert TaskStatus.STOPPED.is_terminal is True
        assert TaskStatus.COMPLETED.is_terminal is True
        assert TaskStatus.ERROR.is_terminal is True
        assert TaskStatus.TIMEOUT.is_terminal is True

        # 非终态
        assert TaskStatus.PENDING.is_terminal is False
        assert TaskStatus.RUNNING.is_terminal is False
        assert TaskStatus.STOPPING.is_terminal is False

    def test_can_stop(self):
        """测试是否可以停止"""
        assert TaskStatus.RUNNING.can_stop is True

        assert TaskStatus.PENDING.can_stop is False
        assert TaskStatus.STOPPING.can_stop is False
        assert TaskStatus.STOPPED.can_stop is False


# ==============================================================================
# TaskStateMachine 状态机测试
# ==============================================================================

class TestTaskStateMachine:
    """任务状态机测试"""

    def test_init(self):
        """测试初始化"""
        sm = TaskStateMachine(TaskStatus.PENDING)
        assert sm.status == TaskStatus.PENDING
        assert len(sm.history) == 1  # 初始状态记录

    def test_can_transition_to(self):
        """测试状态转换检查"""
        sm = TaskStateMachine(TaskStatus.PENDING)

        # PENDING 可以转换到 RUNNING 和 ERROR
        assert sm.can_transition_to(TaskStatus.RUNNING) is True
        assert sm.can_transition_to(TaskStatus.ERROR) is True

        # PENDING 不能直接转换到 STOPPED
        assert sm.can_transition_to(TaskStatus.STOPPED) is False

    def test_transition_to_success(self):
        """测试成功状态转换"""
        sm = TaskStateMachine(TaskStatus.PENDING)

        result = sm.transition_to(TaskStatus.RUNNING, reason="test")

        assert result is True
        assert sm.status == TaskStatus.RUNNING
        assert len(sm.history) == 2

    def test_transition_to_invalid(self):
        """测试无效状态转换"""
        sm = TaskStateMachine(TaskStatus.PENDING)

        # PENDING -> STOPPED 是无效转换
        result = sm.transition_to(TaskStatus.STOPPED, reason="test")

        assert result is False
        assert sm.status == TaskStatus.PENDING  # 状态不变

    def test_observer(self):
        """测试状态观察者"""
        sm = TaskStateMachine(TaskStatus.PENDING)

        events = []

        def observer(event: StatusChangeEvent):
            events.append(event)

        sm.add_observer(observer)
        sm.transition_to(TaskStatus.RUNNING, reason="start")

        assert len(events) == 1
        assert events[0].to_status == TaskStatus.RUNNING
        assert events[0].reason == "start"

    def test_history(self):
        """测试状态历史记录"""
        sm = TaskStateMachine(TaskStatus.PENDING)
        sm.transition_to(TaskStatus.RUNNING, reason="start", metadata={"key": "value"})

        history = sm.history

        assert len(history) == 2
        assert history[0].to_status == TaskStatus.PENDING
        assert history[1].to_status == TaskStatus.RUNNING
        assert history[1].reason == "start"


# ==============================================================================
# BackgroundTask + 状态机测试
# ==============================================================================

class TestBackgroundTaskWithStateMachine:
    """使用状态机的后台任务测试"""

    @pytest.fixture
    def mock_channel(self):
        """创建模拟的shell channel"""
        channel = MagicMock()
        channel.active = True
        channel.closed = False
        channel.recv_ready.return_value = False
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False
        channel.recv.return_value = b""
        channel.recv_stderr.return_value = b""
        return channel

    def test_init_with_state_machine(self, mock_channel):
        """测试任务初始化使用状态机"""
        task = BackgroundTask(
            channel=mock_channel,
            command="echo test",
            buffer_size_mb=1.0,
        )

        # 验证状态机初始化
        assert isinstance(task._state_machine, TaskStateMachine)
        assert task.status == TaskStatus.RUNNING
        assert task.status_str == "running"
        assert task.is_running() is True

        # 验证历史记录
        assert len(task._state_machine.history) >= 2  # PENDING -> RUNNING

    def test_status_transitions(self, mock_channel):
        """测试状态流转"""
        task = BackgroundTask(
            channel=mock_channel,
            command="sleep 10",
            cleanup_delay=0.1,
        )

        # 初始状态
        assert task.status == TaskStatus.RUNNING

        # 停止任务
        task.stop(graceful=False)
        time.sleep(0.2)

        # 验证状态流转：RUNNING -> STOPPING -> STOPPED
        assert task.is_stopped() is True

        # 验证历史
        history = task._state_machine.history
        status_values = [e.to_status for e in history]
        assert TaskStatus.STOPPED in status_values

    def test_stop_sends_sigint_in_shell_mode(self, mock_channel):
        """测试Shell模式下发送SIGINT"""
        task = BackgroundTask(
            channel=mock_channel,
            command="tcpdump -i eth0",
        )

        task.stop(graceful=True, timeout=0.1)

        # 验证发送了 Ctrl+C (\x03)
        mock_channel.send.assert_called_with(b'\x03')

    def test_state_observer_logs_transitions(self, mock_channel, caplog):
        """测试状态变更触发日志"""
        import logging

        with caplog.at_level(logging.INFO):
            task = BackgroundTask(
                channel=mock_channel,
                command="test",
            )
            task.stop(graceful=False)

        # 验证状态变更被记录
        assert "状态:" in caplog.text

    def test_terminal_state_triggers_cleanup(self, mock_channel):
        """测试终态触发清理"""
        # 需要 manager 才能设置清理定时器
        from rprobe.core.async_executor import BackgroundTaskManager
        mock_client = MagicMock()
        manager = BackgroundTaskManager(mock_client)

        task = BackgroundTask(
            channel=mock_channel,
            command="test",
            cleanup_delay=0.1,
        )
        task._manager = manager  # 绑定 manager

        task.stop(graceful=False)
        time.sleep(0.2)

        # 验证清理定时器被设置
        assert task._cleanup_timer is not None

    def test_get_summary_includes_status_history(self, mock_channel):
        """测试摘要包含状态历史"""
        task = BackgroundTask(
            channel=mock_channel,
            command="test",
        )

        task.stop(graceful=False)
        time.sleep(0.1)

        summary = task.get_summary()

        assert summary.status_enum == TaskStatus.STOPPED
        assert summary.status == "stopped"
        assert len(summary.status_history) > 0


# ==============================================================================
# BackgroundTaskManager + 强制Shell模式测试
# ==============================================================================

class TestBackgroundTaskManagerShellMode:
    """测试强制Shell模式"""

    @pytest.fixture
    def mock_ssh_client_pool(self):
        """创建使用连接池的 mock SSH client"""
        client = MagicMock()
        client._use_pool = True

        # 模拟连接池
        mock_conn = MagicMock()
        mock_conn.transport = MagicMock()
        mock_channel = MagicMock()
        mock_channel.active = True
        mock_channel.closed = False
        mock_conn.transport.open_session.return_value = mock_channel

        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=None)

        client._pool = MagicMock()
        client._pool.get_connection.return_value = mock_context

        return client, mock_channel

    @pytest.fixture
    def mock_ssh_client_direct(self):
        """创建直连模式的 mock SSH client"""
        client = MagicMock()
        client._use_pool = False

        mock_channel = MagicMock()
        mock_channel.active = True
        mock_channel.closed = False

        client._connection = MagicMock()
        client._connection.transport = MagicMock()
        client._connection.transport.open_session.return_value = mock_channel

        return client, mock_channel

    def test_run_creates_shell_channel_in_pool_mode(self, mock_ssh_client_pool):
        """测试连接池模式下创建Shell Channel"""
        client, mock_channel = mock_ssh_client_pool
        manager = BackgroundTaskManager(client)

        task = manager.run("tcpdump -i eth0")

        # 验证从连接池获取连接
        client._pool.get_connection.assert_called_once()

        # 验证创建了 shell channel（调用了 get_pty 和 invoke_shell）
        mock_channel.get_pty.assert_called_once()
        mock_channel.invoke_shell.assert_called_once()

        # 验证发送了命令
        mock_channel.send.assert_called_with("tcpdump -i eth0\n")

    def test_run_creates_shell_channel_in_direct_mode(self, mock_ssh_client_direct):
        """测试直连模式下创建Shell Channel"""
        client, mock_channel = mock_ssh_client_direct
        manager = BackgroundTaskManager(client)

        task = manager.run("sleep 10")

        # 验证确保连接
        client._connection.ensure_connected.assert_called_once()

        # 验证创建了 shell channel
        mock_channel.get_pty.assert_called_once()
        mock_channel.invoke_shell.assert_called_once()

    def test_run_with_name(self, mock_ssh_client_direct):
        """测试带名称的任务"""
        client, _ = mock_ssh_client_direct
        manager = BackgroundTaskManager(client)

        task = manager.run("command", name="my_task")

        assert task.name == "my_task"
        assert manager.get_by_name("my_task") == task

    def test_run_duplicate_name_raises(self, mock_ssh_client_direct):
        """测试重复名称抛出异常"""
        client, _ = mock_ssh_client_direct
        manager = BackgroundTaskManager(client)

        manager.run("cmd1", name="task1")

        with pytest.raises(ValueError) as exc_info:
            manager.run("cmd2", name="task1")

        assert "已存在" in str(exc_info.value)

    def test_stop_all_tasks(self, mock_ssh_client_direct):
        """测试停止所有任务"""
        client, _ = mock_ssh_client_direct
        manager = BackgroundTaskManager(client)

        task1 = manager.run("cmd1")
        task2 = manager.run("cmd2")

        manager.stop_all(graceful=False)

        assert not task1.is_running()
        assert not task2.is_running()

    def test_list_running(self, mock_ssh_client_direct):
        """测试列出运行中的任务"""
        client, mock_channel = mock_ssh_client_direct
        # 保持 channel active，避免立即变成 ERROR
        mock_channel.exit_status_ready = False
        mock_channel.active = True
        mock_channel.closed = False

        manager = BackgroundTaskManager(client)
        task = manager.run("sleep 100")

        running = manager.list_running()

        assert len(running) == 1
        assert running[0] == task


# ==============================================================================
# 集成测试
# ==============================================================================

class TestBackgroundTaskIntegration:
    """集成测试"""

    @pytest.fixture
    def mock_channel_with_output(self):
        """创建会产生输出的 mock channel"""
        channel = MagicMock()
        channel.active = True
        channel.closed = False

        # 模拟输出
        output_data = [b"Line 1\n", b"Line 2\n", b""]
        output_index = [0]

        def mock_recv(*args, **kwargs):
            if output_index[0] < len(output_data):
                data = output_data[output_index[0]]
                output_index[0] += 1
                return data
            return b""

        channel.recv_ready.side_effect = lambda: output_index[0] < len(output_data)
        channel.recv.side_effect = mock_recv
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready = False

        return channel

    def test_task_captures_output(self, mock_channel_with_output):
        """测试任务捕获输出"""
        task = BackgroundTask(
            channel=mock_channel_with_output,
            command="echo test",
        )

        time.sleep(0.1)

        output = task.get_output()
        assert "Line 1" in output
        assert "Line 2" in output

    def test_full_lifecycle(self, mock_channel_with_output):
        """测试完整生命周期"""
        channel = mock_channel_with_output
        task = BackgroundTask(
            channel=channel,
            command="long_running_command",
            cleanup_delay=0.1,
        )

        # 1. 运行中
        assert task.is_running()

        # 2. 优雅停止
        task.stop(graceful=True, timeout=0.5)

        # 3. 已停止
        assert task.is_stopped()

        # 4. 验证状态历史完整
        history = task._state_machine.history
        statuses = [e.to_status for e in history]
        assert TaskStatus.PENDING in statuses
        assert TaskStatus.RUNNING in statuses
        assert TaskStatus.STOPPED in statuses


# ==============================================================================
# bg 便捷函数测试
# ==============================================================================

class TestBgFunction:
    """测试 bg 便捷函数"""

    def test_bg_creates_manager(self):
        """测试 bg 函数创建管理器"""
        client = MagicMock()
        client._bg_manager = None
        client._use_pool = False
        client._connection = MagicMock()
        client._connection.transport = MagicMock()

        mock_channel = MagicMock()
        mock_channel.active = True
        mock_channel.closed = False
        client._connection.transport.open_session.return_value = mock_channel

        task = bg(client, "echo test")

        assert client._bg_manager is not None
        assert isinstance(client._bg_manager, BackgroundTaskManager)

    def test_bg_uses_existing_manager(self):
        """测试 bg 函数复用现有管理器"""
        client = MagicMock()
        existing_manager = MagicMock()
        existing_manager.run.return_value = MagicMock()
        client._bg_manager = existing_manager

        task = bg(client, "echo test")

        existing_manager.run.assert_called_once()
