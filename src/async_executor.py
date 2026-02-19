"""
异步命令执行模块 - 后台任务管理
支持非阻塞长时间命令执行，字节限制环形缓冲区，自动清理
"""

import threading
import time
import uuid
import logging
from collections import deque
from dataclasses import dataclass
from typing import Optional, List, Iterator, Dict
from datetime import datetime

from src.core.models import CommandResult

logger = logging.getLogger(__name__)


class ByteLimitedBuffer:
    """按字节限制的环形缓冲区"""
    
    def __init__(self, max_bytes: int = 10 * 1024 * 1024):  # 默认10MB
        self.max_bytes = max_bytes
        self._buffer: deque = deque()
        self._current_size = 0
        self._lock = threading.Lock()
    
    def append(self, data: str) -> None:
        """添加数据，超出限制时丢弃旧数据"""
        with self._lock:
            data_bytes = len(data.encode('utf-8', errors='ignore'))
            
            # 如果单条数据就超过限制，只保留最后部分
            if data_bytes > self.max_bytes:
                encoded = data.encode('utf-8', errors='ignore')
                truncated = encoded[-self.max_bytes:]
                data = truncated.decode('utf-8', errors='ignore')
                data_bytes = len(data.encode('utf-8', errors='ignore'))
            
            self._buffer.append(data)
            self._current_size += data_bytes
            
            # 清理旧数据直到满足限制
            while self._current_size > self.max_bytes and len(self._buffer) > 1:
                old_data = self._buffer.popleft()
                self._current_size -= len(old_data.encode('utf-8', errors='ignore'))
    
    def extend(self, lines: List[str]) -> None:
        """批量添加多行"""
        for line in lines:
            self.append(line)
    
    def get(self, tail_bytes: Optional[int] = None) -> str:
        """获取内容，可选只返回最后N字节"""
        with self._lock:
            if not self._buffer:
                return ""
            
            if tail_bytes is None:
                return '\n'.join(self._buffer)
            
            # 从后往前取，直到满足字节数
            result = []
            current_bytes = 0
            for line in reversed(self._buffer):
                line_bytes = len(line.encode('utf-8', errors='ignore'))
                if current_bytes + line_bytes > tail_bytes and result:
                    break
                result.append(line)
                current_bytes += line_bytes
            
            return '\n'.join(reversed(result))
    
    def get_lines(self, tail_lines: Optional[int] = None) -> List[str]:
        """获取行列表"""
        with self._lock:
            if tail_lines is None:
                return list(self._buffer)
            return list(self._buffer)[-tail_lines:]
    
    def __len__(self) -> int:
        """返回当前字节数"""
        return self._current_size
    
    @property
    def line_count(self) -> int:
        """返回行数"""
        return len(self._buffer)


@dataclass
class TaskSummary:
    """任务摘要（轻量级结果）"""
    task_id: str
    command: str
    status: str
    exit_code: Optional[int]
    duration: float
    lines_output: int
    lines_stderr: int
    bytes_output: int
    bytes_stderr: int
    last_lines: List[str]  # 最后几行用于快速查看
    remote_files: List[str]  # 检测到的远程文件路径
    start_time: datetime
    end_time: Optional[datetime]
    
    def __str__(self) -> str:
        status_icon = "✓" if self.status == "completed" else "✗" if self.status == "stopped" else "→"
        cmd_display = self.command[:50] + "..." if len(self.command) > 50 else self.command
        return (
            f"[{status_icon}] [{self.task_id}] {cmd_display}\n"
            f"    状态: {self.status} | 退出码: {self.exit_code}\n"
            f"    时长: {self.duration:.1f}s | 输出: {self.lines_output}行/{self.bytes_output}B\n"
            f"    远程文件: {', '.join(self.remote_files) if self.remote_files else '无'}"
        )


class BackgroundTask:
    """后台任务对象 - 管理长时间运行的命令"""
    
    def __init__(
        self, 
        channel, 
        command: str, 
        buffer_size_mb: float = 10.0,
        cleanup_delay: float = 3600.0
    ):
        self.id = str(uuid.uuid4())[:8]
        self.command = command
        self.name: Optional[str] = None
        
        # 字节限制的环形缓冲区
        max_bytes = int(buffer_size_mb * 1024 * 1024)
        self._output_buffer = ByteLimitedBuffer(max_bytes)
        self._stderr_buffer = ByteLimitedBuffer(max_bytes)
        
        self._status = "running"  # running/stopped/completed/error
        self._exit_code: Optional[int] = None
        self._error: Optional[str] = None
        self._start_time = time.time()
        self._end_time: Optional[float] = None
        self._start_datetime = datetime.now()
        self._end_datetime: Optional[datetime] = None
        
        # 统计信息
        self.stats = {
            "lines_output": 0,
            "lines_stderr": 0,
            "bytes_output": 0,
            "bytes_stderr": 0,
        }
        
        # 监控线程
        self._channel = channel
        self._stop_event = threading.Event()
        self._cleanup_delay = cleanup_delay
        self._cleanup_timer: Optional[threading.Timer] = None
        self._manager: Optional['BackgroundTaskManager'] = None
        
        # 启动监控线程
        self._monitor_thread = threading.Thread(target=self._monitor, name=f"TaskMonitor-{self.id}")
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        
        logger.debug(f"后台任务启动 [{self.id}] {command[:60]}...")
    
    # ========== 状态查询 ==========
    
    @property
    def status(self) -> str:
        """当前状态"""
        return self._status
    
    @property
    def exit_code(self) -> Optional[int]:
        """退出码（未完成时None）"""
        return self._exit_code
    
    @property
    def duration(self) -> float:
        """运行时长（秒）"""
        end = self._end_time or time.time()
        return end - self._start_time
    
    def is_running(self) -> bool:
        """是否在运行中"""
        return self._status == "running"
    
    def is_completed(self) -> bool:
        """是否自己正常完成"""
        return self._status == "completed"
    
    def is_stopped(self) -> bool:
        """是否被手动停止"""
        return self._status == "stopped"
    
    def is_failed(self) -> bool:
        """是否出错"""
        return self._status == "error"
    
    # ========== 控制方法 ==========
    
    def stop(self, graceful: bool = True, timeout: float = 5.0) -> bool:
        """
        停止任务
        
        Args:
            graceful: True发送SIGINT(Ctrl+C), False强制关闭
            timeout: 优雅停止的超时时间
        """
        if not self.is_running():
            return True
        
        logger.debug(f"停止任务 [{self.id}] graceful={graceful} timeout={timeout}s")
        
        if graceful:
            try:
                # 方式1: 发送Ctrl+C (SIGINT)
                self._channel.send("\x03")
                # 等待进程结束
                if self._wait_for_exit(timeout):
                    self._status = "stopped"
                    self._end_time = time.time()
                    self._end_datetime = datetime.now()
                    logger.info(
                        f"后台任务停止 [{self.id}] {self.command[:50]}... | "
                        f"时长: {self.duration:.1f}s | 原因: 用户优雅停止"
                    )
                    self._on_complete()
                    return True
            except Exception as e:
                logger.warning(f"优雅停止失败 [{self.id}]: {e}")
        
        # 方式2: 强制关闭
        try:
            self._channel.close()
        except:
            pass
        
        self._status = "stopped"
        self._end_time = time.time()
        self._end_datetime = datetime.now()
        logger.info(
            f"后台任务停止 [{self.id}] {self.command[:50]}... | "
            f"时长: {self.duration:.1f}s | 原因: 用户强制停止"
        )
        self._on_complete()
        return True
    
    def wait(self, timeout: Optional[float] = None) -> bool:
        """等待任务完成"""
        if not self.is_running():
            return True
        
        return self._wait_for_exit(timeout)
    
    def cancel_cleanup(self) -> None:
        """取消自动清理（如果需要在完成后继续保留）"""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()
            self._cleanup_timer = None
            logger.debug(f"任务 [{self.id}] 自动清理已取消")
    
    # ========== 结果获取 ==========
    
    def get_summary(self, tail_lines: int = 10) -> TaskSummary:
        """
        获取任务摘要（轻量级，不返回完整输出）
        
        Args:
            tail_lines: 返回最后N行用于预览
        """
        return TaskSummary(
            task_id=self.id,
            command=self.command,
            status=self._status,
            exit_code=self._exit_code,
            duration=self.duration,
            lines_output=self.stats["lines_output"],
            lines_stderr=self.stats["lines_stderr"],
            bytes_output=len(self._output_buffer),
            bytes_stderr=len(self._stderr_buffer),
            last_lines=self._output_buffer.get_lines(tail_lines),
            remote_files=self._detect_remote_files(),
            start_time=self._start_datetime,
            end_time=self._end_datetime
        )
    
    def get_output(self, tail_bytes: Optional[int] = None) -> str:
        """获取stdout输出"""
        return self._output_buffer.get(tail_bytes)
    
    def get_stderr(self, tail_bytes: Optional[int] = None) -> str:
        """获取stderr输出"""
        return self._stderr_buffer.get(tail_bytes)
    
    def get_result(self, wait: bool = False, timeout: Optional[float] = None) -> Optional[CommandResult]:
        """
        获取完整结果
        
        Args:
            wait: 是否等待任务完成
            timeout: 等待超时时间
        """
        if wait and self.is_running():
            if not self._wait_for_exit(timeout):
                return None
        
        return CommandResult(
            stdout=self.get_output(),
            stderr=self.get_stderr(),
            exit_code=self._exit_code if self._exit_code is not None else -1,
            execution_time=self.duration,
            command=self.command
        )
    
    def iter_output(self, block: bool = True, timeout: Optional[float] = None) -> Iterator[str]:
        """
        迭代器方式读取输出（类似生成器）
        
        Args:
            block: 是否阻塞等待新输出
            timeout: 阻塞超时时间
        """
        last_line_idx = 0
        
        while self.is_running() or last_line_idx < self._output_buffer.line_count:
            lines = self._output_buffer.get_lines()
            
            # yield新行
            while last_line_idx < len(lines):
                yield lines[last_line_idx]
                last_line_idx += 1
            
            if not self.is_running():
                break
            
            if block:
                time.sleep(0.1)
            else:
                break
    
    # ========== 内部方法 ==========
    
    def _monitor(self):
        """后台监控线程"""
        try:
            while not self._stop_event.is_set() and self._channel.active:
                # 读取stdout
                if self._channel.recv_ready():
                    try:
                        data = self._channel.recv(4096).decode('utf-8', errors='replace')
                        self._process_output(data)
                    except Exception as e:
                        logger.debug(f"读取stdout出错 [{self.id}]: {e}")
                
                # 读取stderr
                if self._channel.recv_stderr_ready():
                    try:
                        data = self._channel.recv_stderr(4096).decode('utf-8', errors='replace')
                        self._process_stderr(data)
                    except Exception as e:
                        logger.debug(f"读取stderr出错 [{self.id}]: {e}")
                
                # 检查是否自己结束
                if self._channel.exit_status_ready:
                    try:
                        self._exit_code = self._channel.recv_exit_status()
                        self._status = "completed"
                        self._end_time = time.time()
                        self._end_datetime = datetime.now()
                        self._on_complete()
                    except Exception as e:
                        logger.error(f"获取退出码出错 [{self.id}]: {e}")
                        self._status = "error"
                        self._error = str(e)
                    break
                
                time.sleep(0.01)
        
        except Exception as e:
            logger.error(f"监控线程异常 [{self.id}]: {e}")
            self._status = "error"
            self._error = str(e)
            self._end_time = time.time()
            self._end_datetime = datetime.now()
            self._on_complete()
    
    def _process_output(self, data: str):
        """处理stdout到环形缓冲区"""
        lines = data.split('\n')
        for line in lines:
            if line or lines[-1] == '':  # 保留空行但避免重复
                self._output_buffer.append(line)
                self.stats["lines_output"] += 1
                self.stats["bytes_output"] += len(line.encode('utf-8', errors='ignore'))
    
    def _process_stderr(self, data: str):
        """处理stderr到环形缓冲区"""
        lines = data.split('\n')
        for line in lines:
            if line:
                self._stderr_buffer.append(line)
                self.stats["lines_stderr"] += 1
                self.stats["bytes_stderr"] += len(line.encode('utf-8', errors='ignore'))
    
    def _wait_for_exit(self, timeout: Optional[float] = None) -> bool:
        """等待任务退出"""
        start = time.time()
        while self.is_running():
            if timeout and (time.time() - start) > timeout:
                return False
            time.sleep(0.1)
        return True
    
    def _on_complete(self):
        """任务完成时的处理 - 自动日志和清理"""
        # 记录完成日志
        status_str = "完成" if self.is_completed() else "停止" if self.is_stopped() else "错误"
        logger.info(
            f"后台任务{status_str} [{self.id}] {self.command[:50]}... | "
            f"退出码: {self._exit_code} | "
            f"时长: {self.duration:.1f}s | "
            f"输出: {self.stats['lines_output']}行/{len(self._output_buffer)}B"
        )
        
        # 启动清理定时器
        if self._cleanup_delay > 0 and self._manager:
            self._cleanup_timer = threading.Timer(
                self._cleanup_delay,
                self._cleanup
            )
            self._cleanup_timer.daemon = True
            self._cleanup_timer.start()
            logger.debug(f"任务 [{self.id}] 将在 {self._cleanup_delay}s 后自动清理")
    
    def _cleanup(self):
        """从管理器清理自己"""
        if self._manager:
            self._manager._remove_task(self.id)
            logger.debug(f"任务 [{self.id}] 已从管理器自动清理")
    
    def _detect_remote_files(self) -> List[str]:
        """从命令中检测远程文件路径（简单实现）"""
        import re
        files = []
        
        # 匹配 -w 参数 (tcpdump)
        if "-w " in self.command:
            match = re.search(r'-w\s+(\S+)', self.command)
            if match:
                files.append(match.group(1))
        
        # 匹配 > 重定向
        if ">" in self.command:
            match = re.search(r'>\s+(\S+)', self.command)
            if match:
                files.append(match.group(1))
        
        return files


class BackgroundTaskManager:
    """后台任务管理器"""
    
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
        cleanup_delay: float = 3600.0
    ) -> BackgroundTask:
        """
        启动后台任务
        
        Args:
            command: 要执行的命令
            name: 可选的任务名称（用于后续查找）
            buffer_size_mb: 环形缓冲区大小（MB）
            cleanup_delay: 自动清理延迟（秒）
        
        Raises:
            ValueError: 如果名称已存在
        """
        with self._lock:
            # 检查名称重复
            if name and name in self._tasks_by_name:
                existing = self._tasks_by_name[name]
                raise ValueError(
                    f"任务名称 '{name}' 已存在 | "
                    f"现有任务: {existing.id} ({existing.status}) | "
                    f"请使用其他名称或先停止现有任务"
                )
            
            # 创建channel并执行
            channel = self._client._connection.open_channel()
            channel.exec_command(command)
            
            # 创建任务对象
            task = BackgroundTask(
                channel, 
                command, 
                buffer_size_mb=buffer_size_mb,
                cleanup_delay=cleanup_delay
            )
            task._manager = self
            
            if name:
                task.name = name
                self._tasks_by_name[name] = task
            
            self._tasks[task.id] = task
            
            logger.info(f"后台任务已启动 [{task.id}] {command[:60]}...")
            return task
    
    def get(self, task_id: str) -> Optional[BackgroundTask]:
        """通过ID获取任务"""
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_by_name(self, name: str) -> Optional[BackgroundTask]:
        """通过名称获取任务"""
        with self._lock:
            return self._tasks_by_name.get(name)
    
    @property
    def tasks(self) -> List[BackgroundTask]:
        """获取所有任务列表"""
        with self._lock:
            return list(self._tasks.values())
    
    def list_running(self) -> List[BackgroundTask]:
        """获取运行中的任务"""
        with self._lock:
            return [t for t in self._tasks.values() if t.is_running()]
    
    def list_completed(self) -> List[BackgroundTask]:
        """获取已完成的任务"""
        with self._lock:
            return [t for t in self._tasks.values() if t.is_completed()]
    
    def stop_all(self, graceful: bool = True, timeout: float = 5.0) -> None:
        """停止所有运行中的任务"""
        for task in self.list_running():
            try:
                task.stop(graceful=graceful, timeout=timeout)
            except Exception as e:
                logger.error(f"停止任务失败 [{task.id}]: {e}")
    
    def wait_all(self, timeout: Optional[float] = None) -> bool:
        """等待所有任务完成"""
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
        """获取所有任务摘要"""
        with self._lock:
            return [task.get_summary(tail_lines) for task in self._tasks.values()]
    
    def _remove_task(self, task_id: str) -> None:
        """内部方法：从管理器移除任务（由任务自动调用）"""
        with self._lock:
            task = self._tasks.pop(task_id, None)
            if task and task.name:
                self._tasks_by_name.pop(task.name, None)


# 便捷函数
def bg(
    ssh_client,
    command: str,
    name: Optional[str] = None,
    buffer_size_mb: float = 10.0,
    cleanup_delay: float = 3600.0
) -> BackgroundTask:
    """
    便捷函数：在SSH客户端上启动后台任务
    
    如果客户端没有任务管理器，会自动创建
    """
    if not hasattr(ssh_client, '_bg_manager') or ssh_client._bg_manager is None:
        ssh_client._bg_manager = BackgroundTaskManager(ssh_client)
    
    return ssh_client._bg_manager.run(
        command, 
        name=name,
        buffer_size_mb=buffer_size_mb,
        cleanup_delay=cleanup_delay
    )
