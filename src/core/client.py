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
from typing import Optional, Dict, List

import paramiko

from src.config.models import SSHConfig
from src.core.models import CommandResult
from src.core.connection import ConnectionManager
from src.receivers.smart_receiver import SmartChannelReceiver, create_receiver
from src.session.shell_session import ShellSession
from src.patterns.prompt_detector import PromptDetector
from src.pooling import ConnectionPool, get_pool_manager

logger = logging.getLogger(__name__)


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
        # 支持多个 Shell 会话
        self._shell_sessions: Dict[str, ShellSession] = {}
        self._default_session_id: Optional[str] = None

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

    def connect(self) -> None:
        """
        建立 SSH 连接

        如果使用连接池，此方法不执行任何操作（连接由池管理）。

        Raises:
            paramiko.AuthenticationException: 认证失败
            paramiko.SSHException: SSH 连接错误
            TimeoutError: 连接超时
        """
        if not self._use_pool:
            self._connection.connect()

    def disconnect(self) -> None:
        """
        断开 SSH 连接

        注意：如果使用连接池，连接会归还给池而不是关闭。
        """
        # 关闭所有 shell 会话
        self.close_all_shell_sessions()

        if not self._use_pool:
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
        if self._default_session_id:
            session = self._shell_sessions.get(self._default_session_id)
            return session is not None and session.is_active
        return False

    @property
    def shell_sessions(self) -> List[str]:
        """获取所有活跃的 shell 会话 ID 列表"""
        return [sid for sid, session in self._shell_sessions.items() if session.is_active]

    @property
    def shell_session_count(self) -> int:
        """获取活跃 shell 会话数量"""
        return len(self.shell_sessions)

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
        # 生成会话 ID
        if session_id is None:
            session_id = str(uuid.uuid4())[:8]

        # 检查会话 ID 是否已存在
        if session_id in self._shell_sessions and self._shell_sessions[session_id].is_active:
            raise RuntimeError(f"Shell 会话 '{session_id}' 已存在，请先关闭")

        try:
            if self._use_pool:
                # 使用连接池获取连接
                with self._pool.get_connection() as conn:
                    channel = conn.open_channel(timeout)
                    prompt_detector = PromptDetector()
                    session = ShellSession(channel, self._config, prompt_detector)
                    prompt = session.initialize(timeout)
                    self._shell_sessions[session_id] = session
                    # 设置默认会话（如果还没有）
                    if self._default_session_id is None:
                        self._default_session_id = session_id
                    logger.info(f"Shell 会话 '{session_id}' 已打开，提示符: {prompt}")
                    return prompt
            else:
                # 直接使用连接
                self._connection.ensure_connected()
                channel = self._connection.open_channel(timeout)
                prompt_detector = PromptDetector()
                session = ShellSession(channel, self._config, prompt_detector)
                prompt = session.initialize(timeout)
                self._shell_sessions[session_id] = session
                # 设置默认会话（如果还没有）
                if self._default_session_id is None:
                    self._default_session_id = session_id
                logger.info(f"Shell 会话 '{session_id}' 已打开，提示符: {prompt}")
                return prompt
        except Exception as e:
            # 清理资源
            if session_id in self._shell_sessions:
                del self._shell_sessions[session_id]
            raise RuntimeError(f"打开 Shell 会话失败: {e}") from e

    def close_shell_session(self, session_id: Optional[str] = None) -> None:
        """
        关闭 shell 会话

        Args:
            session_id: 会话 ID（可选，默认关闭默认会话）
        """
        # 如果没有指定 session_id，使用默认会话
        if session_id is None:
            session_id = self._default_session_id

        if session_id is None:
            logger.warning("没有活动的 Shell 会话")
            return

        session = self._shell_sessions.get(session_id)
        if session:
            session.close()
            del self._shell_sessions[session_id]
            logger.info(f"Shell 会话 '{session_id}' 已关闭")

            # 如果关闭的是默认会话，清除默认会话 ID
            if session_id == self._default_session_id:
                self._default_session_id = None
                # 如果有其他活跃会话，将第一个设为默认
                if self.shell_sessions:
                    self._default_session_id = self.shell_sessions[0]
        else:
            logger.warning(f"Shell 会话 '{session_id}' 不存在")

    def close_all_shell_sessions(self) -> None:
        """关闭所有 shell 会话"""
        session_ids = list(self._shell_sessions.keys())
        for session_id in session_ids:
            try:
                self.close_shell_session(session_id)
            except Exception as e:
                logger.warning(f"关闭会话 '{session_id}' 时出错: {e}")
        self._default_session_id = None

    def get_shell_session(self, session_id: str) -> Optional[ShellSession]:
        """
        获取指定 shell 会话

        Args:
            session_id: 会话 ID

        Returns:
            ShellSession: 会话对象，如果不存在返回 None
        """
        return self._shell_sessions.get(session_id)

    def set_default_shell_session(self, session_id: str) -> None:
        """
        设置默认 shell 会话

        Args:
            session_id: 会话 ID
        """
        if session_id not in self._shell_sessions:
            raise RuntimeError(f"Shell 会话 '{session_id}' 不存在")
        self._default_session_id = session_id
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
            session_id = self._default_session_id

        if session_id is None:
            raise RuntimeError("没有活动的 Shell 会话，请先调用 open_shell_session()")

        session = self._shell_sessions.get(session_id)
        if not session:
            raise RuntimeError(f"Shell 会话 '{session_id}' 不存在")

        if not session.is_active:
            raise RuntimeError(f"Shell 会话 '{session_id}' 已关闭")

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
        """使用连接池执行命令"""
        with self._pool.get_connection() as conn:
            transport = conn.transport
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
            finally:
                if channel:
                    try:
                        channel.close()
                    except Exception as e:
                        logger.warning(f"[exec] 关闭通道时出错: {e}")

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
        except paramiko.SSHException:
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

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
        return False
