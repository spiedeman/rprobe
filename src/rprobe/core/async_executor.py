"""
异步命令执行模块 - 后台任务管理
强制使用Shell模式以支持信号发送和输出监控
"""

import threading
import time
import uuid
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, List, Iterator, Dict, Any
from datetime import datetime

from rprobe.core.models import CommandResult
from rprobe.core.task_status import TaskStatus, TaskStateMachine, StatusChangeEvent

logger = logging.getLogger(__name__)


class ByteLimitedBuffer:
    """按字节限制的环形缓冲区"""

    def __init__(self, max_bytes: int = 10 * 1024 * 1024):
        self.max_bytes = max_bytes
        self._buffer: deque = deque()
        self._current_size = 0
        self._lock = threading.Lock()

    def append(self, data: str) -> None:
        """添加数据，超出限制时丢弃旧数据"""
        with self._lock:
            data_bytes = len(data.encode("utf-8", errors="ignore"))

            if data_bytes > self.max_bytes:
                encoded = data.encode("utf-8", errors="ignore")
                truncated = encoded[-self.max_bytes :]
                data = truncated.decode("utf-8", errors="ignore")
                data_bytes = len(data.encode("utf-8", errors="ignore"))

            self._buffer.append(data)
            self._current_size += data_bytes

            while self._current_size > self.max_bytes and len(self._buffer) > 1:
                old_data = self._buffer.popleft()
                self._current_size -= len(old_data.encode("utf-8", errors="ignore"))

    def extend(self, lines: List[str]) -> None:
        """批量添加多行"""
        for line in lines:
            self.append(line)

    def get(self, tail_bytes: Optional[int] = None) -> str:
        """获取内容"""
        with self._lock:
            if not self._buffer:
                return ""

            if tail_bytes is None:
                return "\n".join(self._buffer)

            result = []
            current_bytes = 0
            for line in reversed(self._buffer):
                line_bytes = len(line.encode("utf-8", errors="ignore"))
                if current_bytes + line_bytes > tail_bytes and result:
                    break
                result.append(line)
                current_bytes += line_bytes

            return "\n".join(reversed(result))

    def get_lines(self, tail_lines: Optional[int] = None) -> List[str]:
        """获取行列表"""
        with self._lock:
            if tail_lines is None:
                return list(self._buffer)
            return list(self._buffer)[-tail_lines:]

    def __len__(self) -> int:
        return self._current_size

    @property
    def line_count(self) -> int:
        return len(self._buffer)


@dataclass
class TaskSummary:
    """任务摘要"""
    task_id: str
    command: str
    status: str
    status_enum: TaskStatus
    exit_code: Optional[int]
    duration: float
    lines_output: int
    lines_stderr: int
    bytes_output: int
    bytes_stderr: int
    last_lines: List[str]
    remote_files: List[str]
    start_time: datetime
    end_time: Optional[datetime]
    status_history: List[Dict] = field(default_factory=list)

    def __str__(self) -> str:
        status_icon = {
            TaskStatus.COMPLETED: "✓",
            TaskStatus.STOPPED: "✗",
            TaskStatus.ERROR: "⚠",
            TaskStatus.TIMEOUT: "⏱",
        }.get(self.status_enum, "→")
        cmd_display = self.command[:50] + "..." if len(self.command) > 50 else self.command
        return (
            f"[{status_icon}] [{self.task_id}] {cmd_display}\n"
            f"    状态: {self.status} | 退出码: {self.exit_code}\n"
            f"    时长: {self.duration:.1f}s | 输出: {self.lines_output}行/{self.bytes_output}B"
        )


@dataclass
class BatchTaskResult:
    """批量任务结果"""
    tasks: List[BackgroundTask]
    manager: "BackgroundTaskManager"

    def wait_all(self, timeout: Optional[float] = None) -> bool:
        """等待所有任务完成"""
        return self.manager.wait_all(timeout)

    def stop_all(self, graceful: bool = True, timeout: float = 5.0) -> None:
        """停止所有任务"""
        self.manager.stop_all(graceful, timeout)

    def get_summaries(self, tail_lines: int = 10) -> List[TaskSummary]:
        """获取所有任务摘要"""
        return self.manager.get_all_summaries(tail_lines)

    @property
    def running_count(self) -> int:
        return len(self.manager.list_running())

    @property
    def completed_count(self) -> int:
        return len(self.manager.list_completed())

    @property
    def all_completed(self) -> bool:
        """是否所有任务都已完成"""
        return self.running_count == 0


class BackgroundTask:
    """后台任务对象 - 强制使用Shell模式"""

    # 信号映射（Shell模式支持）
    SIGNAL_MAP = {
        'SIGINT': b'\x03',
        'SIGTERM': b'\x04',
    }

    def __init__(
        self,
        channel,
        command: str,
        buffer_size_mb: float = 10.0,
        cleanup_delay: float = 3600.0,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.command = command
        self.name: Optional[str] = None

        # 使用状态机
        self._state_machine = TaskStateMachine(TaskStatus.PENDING)
        self._state_machine.add_observer(self._on_status_change)

        # 缓冲区
        max_bytes = int(buffer_size_mb * 1024 * 1024)
        self._output_buffer = ByteLimitedBuffer(max_bytes)
        self._stderr_buffer = ByteLimitedBuffer(max_bytes)

        self._exit_code: Optional[int] = None
        self._error: Optional[str] = None
        self._start_time = time.time()
        self._end_time: Optional[float] = None
        self._start_datetime = datetime.now()
        self._end_datetime: Optional[datetime] = None

        self.stats = {
            "lines_output": 0,
            "lines_stderr": 0,
            "bytes_output": 0,
            "bytes_stderr": 0,
        }

        self._channel = channel
        self._stop_event = threading.Event()
        self._cleanup_delay = cleanup_delay
        self._cleanup_timer: Optional[threading.Timer] = None
        self._manager: Optional["BackgroundTaskManager"] = None

        # 启动状态
        self._state_machine.transition_to(TaskStatus.RUNNING, "task_started")

        # 启动监控线程
        self._monitor_thread = threading.Thread(
            target=self._monitor,
            name=f"TaskMonitor-{self.id}"
        )
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

        logger.debug(f"后台任务启动 [{self.id}] {command[:60]}...")

    @property
    def status(self) -> TaskStatus:
        return self._state_machine.status

    @property
    def status_str(self) -> str:
        return self._state_machine.status.value

    def is_running(self) -> bool:
        return self._state_machine.status == TaskStatus.RUNNING

    def is_completed(self) -> bool:
        return self._state_machine.status == TaskStatus.COMPLETED

    def is_stopped(self) -> bool:
        return self._state_machine.status == TaskStatus.STOPPED

    def is_failed(self) -> bool:
        return self._state_machine.status in {TaskStatus.ERROR, TaskStatus.TIMEOUT}

    @property
    def duration(self) -> float:
        end = self._end_time or time.time()
        return end - self._start_time

    @property
    def exit_code(self) -> Optional[int]:
        return self._exit_code

    def stop(self, graceful: bool = True, timeout: float = 5.0) -> bool:
        """停止任务 - Shell模式发送SIGINT"""
        status = self._state_machine.status

        if not status.can_stop:
            return True

        logger.debug(f"停止任务 [{self.id}] graceful={graceful} timeout={timeout}s")

        self._state_machine.transition_to(
            TaskStatus.STOPPING,
            reason="user_stop_requested",
            graceful=graceful
        )

        if graceful:
            success = self._send_signal_and_wait(timeout)
            if success:
                self._state_machine.transition_to(
                    TaskStatus.STOPPED,
                    reason="graceful_stop_success"
                )
                return True
            logger.warning(f"任务 [{self.id}] 优雅停止超时")

        self._force_close()
        return True

    def _send_signal_and_wait(self, timeout: float) -> bool:
        """发送SIGINT并等待退出"""
        try:
            self._channel.send(self.SIGNAL_MAP['SIGINT'])
            logger.debug(f"任务 [{self.id}] 已发送 SIGINT")

            start = time.time()
            while time.time() - start < timeout:
                if not self.is_running():
                    return True
                time.sleep(0.1)
            return False
        except Exception as e:
            logger.error(f"发送信号失败 [{self.id}]: {e}")
            return False

    def _force_close(self):
        """强制关闭channel"""
        try:
            self._channel.close()
            self._state_machine.transition_to(
                TaskStatus.STOPPED,
                reason="force_close"
            )
        except Exception as e:
            self._state_machine.transition_to(
                TaskStatus.ERROR,
                reason="force_close_failed",
                error=str(e)
            )

    def wait(self, timeout: Optional[float] = None) -> bool:
        """等待任务完成"""
        if not self.is_running():
            return True

        start = time.time()
        while self.is_running():
            if timeout and (time.time() - start) > timeout:
                self._state_machine.transition_to(
                    TaskStatus.TIMEOUT,
                    reason="wait_timeout"
                )
                return False
            time.sleep(0.1)
        return True

    def cancel_cleanup(self) -> None:
        """取消自动清理"""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
            self._cleanup_timer = None
            logger.debug(f"任务 [{self.id}] 自动清理已取消")

    def get_summary(self, tail_lines: int = 10) -> TaskSummary:
        """获取任务摘要"""
        return TaskSummary(
            task_id=self.id,
            command=self.command,
            status=self.status_str,
            status_enum=self.status,
            exit_code=self._exit_code,
            duration=self.duration,
            lines_output=self.stats["lines_output"],
            lines_stderr=self.stats["lines_stderr"],
            bytes_output=len(self._output_buffer),
            bytes_stderr=len(self._stderr_buffer),
            last_lines=self._output_buffer.get_lines(tail_lines),
            remote_files=self._detect_remote_files(),
            start_time=self._start_datetime,
            end_time=self._end_datetime,
            status_history=[
                {
                    "timestamp": e.timestamp.isoformat(),
                    "from": e.from_status.value if e.from_status else None,
                    "to": e.to_status.value,
                    "reason": e.reason,
                }
                for e in self._state_machine.history
            ],
        )

    def get_output(self, tail_bytes: Optional[int] = None) -> str:
        return self._output_buffer.get(tail_bytes)

    def get_stderr(self, tail_bytes: Optional[int] = None) -> str:
        return self._stderr_buffer.get(tail_bytes)

    def _monitor(self):
        """后台监控线程"""
        try:
            while not self._stop_event.is_set() and self._channel.active:
                # 读取输出
                self._read_output()

                # 检查channel状态
                if not self._channel.active or self._channel.closed:
                    self._handle_channel_close()
                    break

                # 检查exit_status
                try:
                    if hasattr(self._channel, 'exit_status_ready') and \
                       self._channel.exit_status_ready():
                        exit_code = self._channel.recv_exit_status()
                        self._exit_code = exit_code

                        if exit_code == 0:
                            self._state_machine.transition_to(
                                TaskStatus.COMPLETED,
                                reason="process_exit_success",
                                exit_code=exit_code
                            )
                        elif exit_code == -1:
                            if self._state_machine.status == TaskStatus.STOPPING:
                                self._state_machine.transition_to(
                                    TaskStatus.STOPPED,
                                    reason="process_killed_by_signal"
                                )
                            else:
                                self._state_machine.transition_to(
                                    TaskStatus.ERROR,
                                    reason="process_killed_unexpectedly"
                                )
                        else:
                            self._state_machine.transition_to(
                                TaskStatus.ERROR,
                                reason="process_exit_error",
                                exit_code=exit_code
                            )
                        self._on_complete()
                        break
                except:
                    pass

                time.sleep(0.01)

        except Exception as e:
            logger.error(f"监控线程异常 [{self.id}]: {e}")
            self._state_machine.transition_to(
                TaskStatus.ERROR,
                reason="monitor_exception",
                error=str(e)
            )
            self._on_complete()

    def _read_output(self):
        """读取输出"""
        try:
            if self._channel.recv_ready():
                data = self._channel.recv(4096).decode('utf-8', errors='replace')
                self._process_output(data)
        except:
            pass

        try:
            if self._channel.recv_stderr_ready():
                data = self._channel.recv_stderr(4096).decode('utf-8', errors='replace')
                self._process_stderr(data)
        except:
            pass

    def _handle_channel_close(self):
        """处理channel关闭"""
        if self._state_machine.status == TaskStatus.STOPPING:
            self._state_machine.transition_to(
                TaskStatus.STOPPED,
                reason="process_stopped_by_user"
            )
        elif self._state_machine.status == TaskStatus.RUNNING:
            self._state_machine.transition_to(
                TaskStatus.ERROR,
                reason="channel_closed_unexpectedly"
            )
        self._on_complete()

    def _process_output(self, data: str):
        """处理stdout"""
        lines = data.split("\n")
        for line in lines:
            if line or lines[-1] == "":
                self._output_buffer.append(line)
                self.stats["lines_output"] += 1
                self.stats["bytes_output"] += len(line.encode("utf-8", errors="ignore"))

    def _process_stderr(self, data: str):
        """处理stderr"""
        lines = data.split("\n")
        for line in lines:
            if line:
                self._stderr_buffer.append(line)
                self.stats["lines_stderr"] += 1
                self.stats["bytes_stderr"] += len(line.encode("utf-8", errors="ignore"))

    def _on_complete(self):
        """任务完成处理"""
        status_str = {
            TaskStatus.COMPLETED: "完成",
            TaskStatus.STOPPED: "停止",
            TaskStatus.ERROR: "错误",
            TaskStatus.TIMEOUT: "超时",
        }.get(self._state_machine.status, "未知")
        
        logger.info(
            f"后台任务{status_str} [{self.id}] {self.command[:50]}... | "
            f"退出码: {self._exit_code} | "
            f"时长: {self.duration:.1f}s | "
            f"输出: {self.stats['lines_output']}行/{len(self._output_buffer)}B"
        )

    def _on_status_change(self, event: StatusChangeEvent):
        """状态变更回调"""
        logger.info(
            f"任务 [{self.id}] 状态: "
            f"{event.from_status.value if event.from_status else 'None'} -> "
            f"{event.to_status.value} | {event.reason}"
        )

        if event.to_status.is_terminal:
            self._end_time = time.time()
            self._end_datetime = datetime.now()
            self._schedule_cleanup()

    def _schedule_cleanup(self):
        """调度清理"""
        if self._cleanup_delay > 0 and self._manager:
            self._cleanup_timer = threading.Timer(self._cleanup_delay, self._cleanup)
            self._cleanup_timer.daemon = True
            self._cleanup_timer.start()
            logger.debug(f"任务 [{self.id}] 将在 {self._cleanup_delay}s 后自动清理")

    def _cleanup(self):
        """清理任务"""
        if self._manager:
            self._manager._remove_task(self.id)
            logger.debug(f"任务 [{self.id}] 已从管理器自动清理")

    def _detect_remote_files(self) -> List[str]:
        """检测远程文件路径"""
        import re
        files = []

        if "-w " in self.command:
            match = re.search(r"-w\s+(\S+)", self.command)
            if match:
                files.append(match.group(1))

        if ">" in self.command:
            match = re.search(r">\s+(\S+)", self.command)
            if match:
                files.append(match.group(1))

        return files


class BackgroundTaskManager:
    """后台任务管理器 - 强制使用Shell模式"""

    def __init__(self, ssh_client):
        self._client = ssh_client
        self._tasks: Dict[str, BackgroundTask] = {}
        self._tasks_by_name: Dict[str, BackgroundTask] = {}
        self._lock = threading.Lock()

    def run(
        self,
        command: str,
        name: Optional[str] = None,
        buffer_size_mb: float = 10.0,
        cleanup_delay: float = 3600.0,
    ) -> BackgroundTask:
        """启动后台任务 - 强制使用Shell模式"""
        with self._lock:
            # 检查名称重复
            if name and name in self._tasks_by_name:
                existing = self._tasks_by_name[name]
                raise ValueError(
                    f"任务名称 '{name}' 已存在 | "
                    f"现有任务: {existing.id} ({existing.status.value})"
                )

            # 创建Shell Channel（自动适配连接池/直连）
            channel = self._create_shell_channel()

            # Shell模式：发送命令
            time.sleep(0.5)  # 等待shell初始化
            channel.send(command + "\n")

            # 创建任务
            task = BackgroundTask(
                channel=channel,
                command=command,
                buffer_size_mb=buffer_size_mb,
                cleanup_delay=cleanup_delay,
            )
            task._manager = self

            if name:
                task.name = name
                self._tasks_by_name[name] = task

            self._tasks[task.id] = task

            logger.info(f"后台任务已启动 [{task.id}] {command[:60]}...")
            return task

    def _create_shell_channel(self):
        """创建Shell Channel - 复用现有代码"""
        # 判断连接模式
        if self._client._use_pool:
            # 连接池模式
            connection_context = self._client._pool.get_connection()
            conn = connection_context.__enter__()
            transport = conn.transport
        else:
            # 直连模式
            self._client._connection.ensure_connected()
            transport = self._client._connection.transport

        # 创建shell channel
        channel = transport.open_session()
        channel.get_pty(term='vt100', width=80, height=24)
        channel.invoke_shell()

        return channel

    def get(self, task_id: str) -> Optional[BackgroundTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def get_by_name(self, name: str) -> Optional[BackgroundTask]:
        with self._lock:
            return self._tasks_by_name.get(name)

    @property
    def tasks(self) -> List[BackgroundTask]:
        with self._lock:
            return list(self._tasks.values())

    def list_running(self) -> List[BackgroundTask]:
        with self._lock:
            return [t for t in self._tasks.values() if t.is_running()]

    def list_completed(self) -> List[BackgroundTask]:
        with self._lock:
            return [t for t in self._tasks.values() if t.is_completed()]

    def stop_all(self, graceful: bool = True, timeout: float = 5.0) -> None:
        for task in self.list_running():
            try:
                task.stop(graceful=graceful, timeout=timeout)
            except Exception as e:
                logger.error(f"停止任务失败 [{task.id}]: {e}")

    def wait_all(self, timeout: Optional[float] = None) -> bool:
        start = time.time()
        for task in self._tasks.values():
            if task.is_running():
                remaining = None if timeout is None else timeout - (time.time() - start)
                if remaining is not None and remaining <= 0:
                    return False
                if not task.wait(remaining):
                    return False
        return True

    def get_all_summaries(self, tail_lines: int = 10) -> List[TaskSummary]:
        with self._lock:
            return [task.get_summary(tail_lines) for task in self._tasks.values()]

    def _remove_task(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.pop(task_id, None)
            if task and task.name:
                self._tasks_by_name.pop(task.name, None)

    def run_batch(
        self,
        commands: List[Dict[str, Any]],
        max_concurrent: int = 5,
        batch_delay: float = 0.1,
    ) -> BatchTaskResult:
        """
        批量启动后台任务（非阻塞）

        Args:
            commands: 任务列表，每项为 {"command": str, "name": str, ...}
            max_concurrent: 保留参数（向后兼容），不再用于阻塞控制
            batch_delay: 每个任务启动间隔（秒），避免瞬间并发冲击

        Returns:
            BatchTaskResult: 批量任务结果对象

        Example:
            commands = [
                {"command": "tcpdump -i eth0", "name": "capture1"},
                {"command": "tcpdump -i eth1", "name": "capture2"},
                {"command": "tail -f /var/log/app.log", "name": "log_monitor"},
            ]
            batch = manager.run_batch(commands, batch_delay=0.5)

            # 等待所有任务完成
            if batch.wait_all(timeout=300):
                print("所有任务完成")

            # 获取所有结果
            for summary in batch.get_summaries():
                print(f"{summary.name}: {summary.status}")
        """
        tasks = []
        for i, cmd_info in enumerate(commands):
            # 启动任务
            task = self.run(
                command=cmd_info["command"],
                name=cmd_info.get("name"),
                buffer_size_mb=cmd_info.get("buffer_size_mb", 10.0),
                cleanup_delay=cmd_info.get("cleanup_delay", 3600.0),
            )
            tasks.append(task)

            # 任务间延迟，避免瞬间并发
            if i < len(commands) - 1:
                time.sleep(batch_delay)

        return BatchTaskResult(tasks=tasks, manager=self)


def bg(
    ssh_client,
    command: str,
    name: Optional[str] = None,
    buffer_size_mb: float = 10.0,
    cleanup_delay: float = 3600.0,
) -> BackgroundTask:
    """便捷函数：启动后台任务"""
    if not hasattr(ssh_client, "_bg_manager") or ssh_client._bg_manager is None:
        ssh_client._bg_manager = BackgroundTaskManager(ssh_client)

    return ssh_client._bg_manager.run(
        command, name=name, buffer_size_mb=buffer_size_mb, cleanup_delay=cleanup_delay
    )


__all__ = [
    'BackgroundTask',
    'BackgroundTaskManager',
    'TaskSummary',
    'BatchTaskResult',
    'ByteLimitedBuffer',
    'bg',
    'TaskStatus',
    'TaskStateMachine',
]
