"""
SSH 客户端模块（重构版）
提供可复用的 SSH 连接和命令执行功能

此模块采用外观模式(Facade Pattern)，协调以下组件：
- ConnectionManager: 管理 SSH 连接
- ChannelDataReceiver: 接收通道数据
- ShellSession: 管理持久 Shell 会话
- PromptDetector: 检测和清理提示符
"""

import logging
import socket
import time
import uuid
from typing import Optional, Dict, List, Callable

# 移除：import paramiko
# 改为从后端导入异常
from src.backends import AuthenticationError, SSHException, ConnectionError

from src.config.models import SSHConfig
from src.core.models import CommandResult
from src.core.connection import ConnectionManager, MultiSessionManager
from src.core.connection_factory import ConnectionFactory
from src.receivers.smart_receiver import SmartChannelReceiver, create_receiver
from src.session.shell_session import ShellSession
from src.patterns.prompt_detector import PromptDetector
from src.pooling import ConnectionPool, get_pool_manager

# 延迟导入避免循环依赖
_stream_executor_class = None

def _get_stream_executor_class():
    """延迟获取 StreamExecutor 类"""
    global _stream_executor_class
    if _stream_executor_class is None:
        from src.core.stream_executor import StreamExecutor
        _stream_executor_class = StreamExecutor
    return _stream_executor_class

logger = logging.getLogger(__name__)


# 延迟导入避免循环依赖
_background_manager_class = None

def _get_background_manager_class():
    global _background_manager_class
    if _background_manager_class is None:
        from src.async_executor import BackgroundTaskManager
        _background_manager_class = BackgroundTaskManager
    return _background_manager_class


class SSHClient:
    """
    SSH 客户端类（外观模式）

    提供简洁的 API 用于 SSH 连接和命令执行，
    支持连接池以优化性能和资源使用。

    Example:
        config = SSHConfig(
            host="example.com",
            username="user",
            password="password"
        )

        # 方式1: 使用连接池（推荐用于频繁操作）
        client = SSHClient(config, use_pool=True)

        # 方式2: 不使用连接池（简单的单次操作）
        client = SSHClient(config, use_pool=False)

        # 使用 exec 通道
        result = client.exec_command("ls -la")
        print(result.stdout)

        # 使用 shell 通道（持久会话）
        client.open_shell_session()
        result = client.shell_command("cd /tmp && pwd")
        print(result.stdout)
        client.close_shell_session()

        client.disconnect()
    """

    def __init__(self, config: SSHConfig, use_pool: bool = False, **pool_kwargs):
        """
        初始化 SSH 客户端

        Args:
            config: SSH 连接配置
            use_pool: 是否使用连接池
            **pool_kwargs: 连接池配置参数
                - max_size: 最大连接数（默认10）
                - min_size: 最小连接数（默认1）
                - max_idle: 最大空闲时间（默认300秒）
                - max_age: 最大连接寿命（默认3600秒）
        """
        self._config = config
        self._use_pool = use_pool
        self._receiver = create_receiver(config)
        # 后台任务管理器
        self._bg_manager = None

        if use_pool:
            # 从全局连接池管理器获取或创建连接池
            self._pool = get_pool_manager().get_or_create_pool(config, **pool_kwargs)
            self._connection = None
            logger.debug(f"SSHClient 初始化完成（使用连接池）: {config.host}:{config.port}")
        else:
            # 不使用连接池，直接创建连接管理器
            self._pool = None
            self._connection = ConnectionManager(config)
            logger.debug(
                f"SSHClient 初始化完成: {config.host}:{config.port}, 接收模式: {self._receiver.mode}"
            )

        # 初始化多会话管理器（统一处理 Shell 会话）
        self._session_manager = MultiSessionManager(
            connection=self._connection if not use_pool else None,
            config=config,
            use_pool=use_pool,
            pool=self._pool if use_pool else None,
        )

    def connect(self) -> None:
        """
        建立 SSH 连接

        如果使用连接池，此方法不执行任何操作（连接由池管理）。

        Raises:
            AuthenticationError: 认证失败
            SSHException: SSH 连接错误
            ConnectionError: 连接错误
        """
        if not self._use_pool:
            self._connection.connect()

    def disconnect(self) -> None:
        """
        断开 SSH 连接

        注意：如果使用连接池，会关闭整个连接池。
        """
        # 停止所有后台任务
        self.stop_all_background()
        
        # 关闭所有 shell 会话
        self.close_all_shell_sessions()

        if self._use_pool and self._pool:
            # 关闭连接池
            self._pool.close()
            self._pool = None
        elif self._connection:
            self._connection.disconnect()

    @property
    def is_connected(self) -> bool:
        """检查连接是否活跃"""
        if self._use_pool:
            # 连接池模式下，认为始终可用（实际连接由池管理）
            return True
        return self._connection.is_connected

    @property
    def shell_session_active(self) -> bool:
        """检查默认 shell 会话是否活跃（向后兼容）"""
        default_session = self._session_manager.get_default_session()
        return default_session is not None

    @property
    def shell_sessions(self) -> List[str]:
        """获取所有活跃的 shell 会话 ID 列表"""
        return self._session_manager.list_sessions()

    @property
    def shell_session_count(self) -> int:
        """获取活跃 shell 会话数量"""
        return self._session_manager.active_session_count

    def open_shell_session(
        self, timeout: Optional[float] = None, session_id: Optional[str] = None
    ) -> str:
        """
        打开一个持久的 shell 会话

        Args:
            timeout: 等待 shell 就绪的超时时间（秒）
            session_id: 会话 ID（可选，默认自动生成）

        Returns:
            str: 检测到的 shell 提示符
        """
        # 生成会话 ID（如果未提供）
        if session_id is None:
            session_id = str(uuid.uuid4())[:8]

        try:
            # 使用 MultiSessionManager 创建会话
            session = self._session_manager.create_session(
                session_id=session_id,
                timeout=timeout,
                set_as_default=True,  # 如果没有默认会话，设为默认
            )

            # 获取提示符（从 session 的 prompt_detector）
            prompt = session.prompt_detector.detect_prompt() if hasattr(session, 'prompt_detector') else ""

            logger.info(f"Shell 会话 '{session_id}' 已打开，提示符: {prompt}")
            return prompt

        except Exception as e:
            logger.error(f"打开 Shell 会话失败: {e}")
            raise RuntimeError(f"打开 Shell 会话失败: {e}") from e

    def close_shell_session(self, session_id: Optional[str] = None) -> None:
        """
        关闭 shell 会话

        Args:
            session_id: 会话 ID（可选，默认关闭默认会话）
        """
        # 如果没有指定 session_id，使用默认会话
        if session_id is None:
            session_id = self._session_manager.get_default_session_id()

        if session_id is None:
            logger.warning("没有活动的 Shell 会话")
            return

        # 使用 MultiSessionManager 关闭会话
        success = self._session_manager.close_session(session_id)
        if success:
            logger.info(f"Shell 会话 '{session_id}' 已关闭")
        else:
            logger.warning(f"Shell 会话 '{session_id}' 不存在或已关闭")

    def close_all_shell_sessions(self) -> None:
        """关闭所有 shell 会话"""
        closed_count = self._session_manager.close_all_sessions()
        logger.info(f"已关闭 {closed_count} 个 Shell 会话")

    def get_shell_session(self, session_id: str) -> Optional[ShellSession]:
        """
        获取指定 shell 会话

        Args:
            session_id: 会话 ID

        Returns:
            ShellSession: 会话对象，如果不存在返回 None
        """
        return self._session_manager.get_session(session_id)

    def set_default_shell_session(self, session_id: str) -> None:
        """
        设置默认 shell 会话

        Args:
            session_id: 会话 ID
        """
        self._session_manager.set_default_session(session_id)
        logger.info(f"默认 Shell 会话已设置为 '{session_id}'")

    def shell_command(
        self, command: str, timeout: Optional[float] = None, session_id: Optional[str] = None
    ) -> CommandResult:
        """
        在持久 shell 会话中执行命令

        Args:
            command: 要执行的命令
            timeout: 命令执行超时（秒）
            session_id: 会话 ID（可选，默认使用默认会话）

        Returns:
            CommandResult: 命令执行结果
        """
        # 确定使用哪个会话
        if session_id is None:
            session = self._session_manager.get_default_session()
            if session is None:
                raise RuntimeError("没有活动的 Shell 会话，请先调用 open_shell_session()")
        else:
            session = self._session_manager.get_session(session_id)
            if session is None:
                raise RuntimeError(f"Shell 会话 '{session_id}' 不存在或已关闭")

        start_time = time.time()
        output = session.execute_command(command, timeout)
        execution_time = time.time() - start_time

        return CommandResult(
            stdout=output, stderr="", exit_code=0, execution_time=execution_time, command=command
        )

    def exec_command(self, command: str, timeout: Optional[float] = None) -> CommandResult:
        """
        通过 exec 通道执行命令

        支持连接池模式和非连接池模式。

        Args:
            command: 要执行的命令
            timeout: 命令执行超时（秒）

        Returns:
            CommandResult: 命令执行结果
        """
        cmd_timeout = timeout or self._config.command_timeout
        start_time = time.time()

        logger.info(f"[exec] 执行命令: {command}")

        if self._use_pool:
            # 使用连接池执行命令
            return self._exec_with_pool(command, cmd_timeout, start_time)
        else:
            # 直接使用连接执行命令
            return self._exec_direct(command, cmd_timeout, start_time)

    def _exec_with_pool(self, command: str, cmd_timeout: float, start_time: float) -> CommandResult:
        """使用连接池执行命令（使用 ConnectionFactory）"""
        with ConnectionFactory.create_exec_channel(
            connection_source=self._pool,
            use_pool=True,
            command=command,
            timeout=cmd_timeout
        ) as channel:
            transport = channel.get_transport()
            stdout_data, stderr_data, exit_code = self._receiver.recv_all(
                channel, timeout=cmd_timeout, transport=transport
            )

            execution_time = time.time() - start_time

            logger.info(
                f"[exec] 命令执行完成: exit_code={exit_code}, " f"耗时={execution_time:.3f}秒"
            )

            return CommandResult(
                stdout=stdout_data,
                stderr=stderr_data,
                exit_code=exit_code,
                execution_time=execution_time,
                command=command,
            )

    def _exec_direct(self, command: str, cmd_timeout: float, start_time: float) -> CommandResult:
        """直接执行命令（不使用连接池）"""
        self._connection.ensure_connected()

        transport = self._connection.transport
        channel = transport.open_session()

        try:
            channel.settimeout(cmd_timeout)
            channel.exec_command(command)

            stdout_data, stderr_data, exit_code = self._receiver.recv_all(
                channel, timeout=cmd_timeout, transport=transport
            )

            execution_time = time.time() - start_time

            logger.info(
                f"[exec] 命令执行完成: exit_code={exit_code}, " f"耗时={execution_time:.3f}秒"
            )

            return CommandResult(
                stdout=stdout_data,
                stderr=stderr_data,
                exit_code=exit_code,
                execution_time=execution_time,
                command=command,
            )
        except TimeoutError:
            raise
        except ConnectionError:
            raise
        except SSHException:
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[exec] 命令执行异常 ({execution_time:.3f}秒): {command} - {e}")
            raise RuntimeError(f"命令执行失败: {e}") from e
        finally:
            if channel:
                try:
                    channel.close()
                except Exception as e:
                    logger.warning(f"[exec] 关闭通道时出错: {e}")

    def exec_command_stream(
        self,
        command: str,
        chunk_handler: Callable[[bytes, bytes], None],
        timeout: Optional[float] = None
    ) -> CommandResult:
        """
        流式执行命令，实时处理数据块
        
        适用于超大数据传输，避免内存占用过高。
        通过回调函数实时处理每个数据块。
        
        注意：这是外观方法，实际执行逻辑在 StreamExecutor 中。
        
        Args:
            command: 要执行的命令
            chunk_handler: 回调函数，接收 (stdout_chunk, stderr_chunk)
                          每次收到数据块时调用
            timeout: 命令执行超时（秒）
            
        Returns:
            CommandResult: 命令执行结果（stdout/stderr 为空字符串，
                          数据已通过 chunk_handler 处理）
            
        Raises:
            TimeoutError: 命令执行超时
            ConnectionError: 连接断开
            RuntimeError: 其他执行错误
            
        Example:
            total_size = 0
            
            def handle_chunk(stdout, stderr):
                global total_size
                total_size += len(stdout)
                print(f"收到 {len(stdout)} 字节")
            
            result = client.exec_command_stream(
                "cat large_file",
                handle_chunk,
                timeout=60.0
            )
            print(f"总共接收: {total_size} 字节")
        """
        StreamExecutor = _get_stream_executor_class()
        executor = StreamExecutor(self)
        return executor.execute(command, chunk_handler, timeout)

    # ========== 后台任务方法 ==========

    def bg(
        self,
        command: str,
        name: Optional[str] = None,
        buffer_size_mb: float = 10.0,
        cleanup_delay: float = 3600.0
    ):
        """
        启动后台任务（非阻塞执行长时间命令）

        Args:
            command: 要执行的命令
            name: 可选的任务名称（用于后续查找）
            buffer_size_mb: 环形缓冲区大小（MB），默认10MB
            cleanup_delay: 自动清理延迟（秒），默认1小时

        Returns:
            BackgroundTask: 任务对象，可用于查询状态、停止、获取结果

        Raises:
            ValueError: 如果名称已存在

        Example:
            # 启动tcpdump
            task = client.bg("tcpdump -i eth0 -w capture.pcap", name="capture")

            # 主线程做其他事
            time.sleep(60)

            # 检查状态
            if task.is_running():
                print(f"运行了 {task.duration} 秒")

            # 停止任务
            task.stop()

            # 获取摘要（轻量级）
            summary = task.get_summary()
            print(summary)
        """
        # 确保已连接
        if not self.is_connected:
            self.connect()

        if self._bg_manager is None:
            manager_class = _get_background_manager_class()
            self._bg_manager = manager_class(self)

        return self._bg_manager.run(
            command,
            name=name,
            buffer_size_mb=buffer_size_mb,
            cleanup_delay=cleanup_delay
        )

    @property
    def background_tasks(self) -> List:
        """获取所有后台任务列表"""
        if self._bg_manager:
            return self._bg_manager.tasks
        return []

    def get_background_task(self, task_id: str):
        """通过ID获取后台任务"""
        if self._bg_manager:
            return self._bg_manager.get(task_id)
        return None

    def get_background_task_by_name(self, name: str):
        """通过名称获取后台任务"""
        if self._bg_manager:
            return self._bg_manager.get_by_name(name)
        return None

    def stop_all_background(self, graceful: bool = True, timeout: float = 5.0) -> None:
        """
        停止所有后台任务

        Args:
            graceful: True发送SIGINT优雅停止，False强制关闭
            timeout: 优雅停止的超时时间
        """
        if self._bg_manager:
            self._bg_manager.stop_all(graceful=graceful, timeout=timeout)

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
        return False
