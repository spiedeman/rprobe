"""
SSH 连接管理模块
提供 SSH 连接的生命周期管理
"""
import logging
import threading
import time
from typing import Optional, List, Dict, TYPE_CHECKING
from dataclasses import dataclass, field

import paramiko

from src.config.models import SSHConfig

if TYPE_CHECKING:
    from src.session.shell_session import ShellSession

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    SSH 连接管理器

    负责建立、维护和关闭 SSH 连接。
    提供连接状态检查和自动重连功能。
    """

    def __init__(self, config: SSHConfig):
        """
        初始化连接管理器

        Args:
            config: SSH 连接配置
        """
        self._config = config
        self._client: Optional[paramiko.SSHClient] = None
        self._transport: Optional[paramiko.Transport] = None

    @property
    def is_connected(self) -> bool:
        """检查连接是否活跃"""
        if not self._transport:
            return False
        return self._transport.is_active()

    @property
    def transport(self) -> Optional[paramiko.Transport]:
        """获取传输层对象"""
        return self._transport

    def connect(self) -> None:
        """
        建立 SSH 连接

        Raises:
            paramiko.AuthenticationException: 认证失败
            paramiko.SSHException: SSH 连接错误
            TimeoutError: 连接超时
        """
        if self.is_connected:
            logger.debug(f"SSH 连接已存在: {self._config.host}")
            return

        logger.info(f"正在连接 SSH 服务器: {self._config.host}:{self._config.port}")

        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": self._config.host,
            "port": self._config.port,
            "username": self._config.username,
            "timeout": self._config.timeout,
            "allow_agent": False,
            "look_for_keys": False,
        }

        auth_method = "password" if self._config.password else "key"
        logger.debug(f"使用 {auth_method} 认证方式")

        if self._config.password:
            connect_kwargs["password"] = self._config.password
        elif self._config.key_filename:
            connect_kwargs["key_filename"] = self._config.key_filename
            if self._config.key_password:
                connect_kwargs["passphrase"] = self._config.key_password

        try:
            self._client.connect(**connect_kwargs)
            self._transport = self._client.get_transport()
            logger.info(f"SSH 连接成功: {self._config.host}")
        except paramiko.AuthenticationException as e:
            logger.error(f"SSH 认证失败: {self._config.host} - {e}")
            self._cleanup()
            raise
        except paramiko.SSHException as e:
            logger.error(f"SSH 连接错误: {self._config.host} - {e}")
            self._cleanup()
            raise
        except Exception as e:
            logger.error(f"SSH 连接异常: {self._config.host} - {e}")
            self._cleanup()
            raise

    def disconnect(self) -> None:
        """断开 SSH 连接"""
        if not self.is_connected:
            return

        logger.info(f"正在断开 SSH 连接: {self._config.host}")
        self._cleanup()
        logger.info(f"SSH 连接已断开: {self._config.host}")

    def _cleanup(self) -> None:
        """清理资源"""
        if self._transport:
            try:
                self._transport.close()
                logger.debug("Transport 已关闭")
            except Exception as e:
                logger.warning(f"关闭 Transport 时出错: {e}")
            self._transport = None

        if self._client:
            try:
                self._client.close()
                logger.debug("SSHClient 已关闭")
            except Exception as e:
                logger.warning(f"关闭 SSHClient 时出错: {e}")
            self._client = None

    def ensure_connected(self) -> None:
        """确保连接已建立，如未连接则自动连接"""
        if not self.is_connected:
            logger.debug("连接未建立，自动连接中...")
            self.connect()

    def open_channel(self, timeout: Optional[float] = None):
        """
        打开新的 SSH 通道

        Args:
            timeout: 超时时间

        Returns:
            paramiko.Channel: 新打开的通道
        """
        self.ensure_connected()
        return self._transport.open_session()

    def open_shell_session(self, timeout: Optional[float] = None) -> paramiko.Channel:
        """
        打开新的 Shell 会话通道

        一个 SSH 连接可以打开多个独立的 Shell 会话，
        每个会话都有自己的 channel 和状态。

        Args:
            timeout: 超时时间

        Returns:
            paramiko.Channel: 配置好的 Shell 会话通道

        Example:
            # 在一个连接上打开多个 shell 会话
            channel1 = conn.open_shell_session()
            channel2 = conn.open_shell_session()

            session1 = ShellSession(channel1, config)
            session2 = ShellSession(channel2, config)

            # 两个会话完全独立
            output1 = session1.execute_command("pwd")
            output2 = session2.execute_command("cd /tmp && pwd")
        """
        self.ensure_connected()
        channel = self._transport.open_session()
        channel.get_pty()
        channel.invoke_shell()
        if timeout:
            channel.settimeout(timeout)
        logger.debug(f"Opened new shell session channel: {channel.get_id()}")
        return channel

    def get_active_channels_count(self) -> int:
        """
        获取当前活跃的通道数量

        Returns:
            int: 活跃通道数
        """
        if not self.is_connected:
            return 0
        return len(self._transport._channels)

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
        return False


@dataclass
class SessionInfo:
    """会话信息"""

    session_id: str
    shell_session: "ShellSession"
    channel: paramiko.Channel
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    command_count: int = 0
    is_active: bool = True

    def mark_used(self) -> None:
        """标记会话被使用"""
        self.last_used = time.time()
        self.command_count += 1


class MultiSessionManager:
    """
    多会话管理器

    在单个 SSH 连接上管理多个独立的 Shell 会话。
    每个会话都有自己的 channel 和状态，完全独立。

    Example:
        from src.core.connection import ConnectionManager, MultiSessionManager

        # 建立连接
        conn = ConnectionManager(config)
        conn.connect()

        # 创建多会话管理器
        session_mgr = MultiSessionManager(conn, config)

        # 创建多个会话
        session1 = session_mgr.create_session("session1")
        session2 = session_mgr.create_session("session2")

        # 在各会话中执行命令（完全独立）
        output1 = session1.execute_command("pwd")  # /home/user
        output2 = session2.execute_command("cd /tmp && pwd")  # /tmp

        # 再次在 session1 执行，目录不变
        output3 = session1.execute_command("pwd")  # /home/user

        # 关闭特定会话
        session_mgr.close_session("session1")

        # 或关闭所有会话
        session_mgr.close_all_sessions()
    """

    def __init__(self, connection: ConnectionManager, config: SSHConfig):
        """
        初始化多会话管理器

        Args:
            connection: SSH 连接管理器
            config: SSH 配置
        """
        self._connection = connection
        self._config = config
        self._sessions: Dict[str, SessionInfo] = {}
        self._lock = threading.RLock()
        self._session_counter = 0

    def create_session(
        self, session_id: Optional[str] = None, timeout: Optional[float] = None
    ) -> "ShellSession":
        """
        创建新的 Shell 会话

        Args:
            session_id: 会话 ID（可选，自动生成）
            timeout: 初始化超时时间

        Returns:
            ShellSession: 新的 Shell 会话

        Raises:
            ValueError: 会话 ID 已存在
            RuntimeError: 连接未建立
        """
        from src.session.shell_session import ShellSession

        with self._lock:
            # 生成会话 ID
            if session_id is None:
                self._session_counter += 1
                session_id = f"session_{self._session_counter}"

            if session_id in self._sessions:
                raise ValueError(f"Session '{session_id}' already exists")

            # 打开新的 channel (使用 open_channel，让 ShellSession.initialize 来初始化)
            channel = self._connection.open_channel(timeout)

            # 创建 ShellSession
            shell_session = ShellSession(channel, self._config)
            shell_session.initialize(timeout)

            # 保存会话信息
            session_info = SessionInfo(
                session_id=session_id, shell_session=shell_session, channel=channel
            )
            self._sessions[session_id] = session_info

            logger.info(f"Created shell session: {session_id}")
            return shell_session

    def get_session(self, session_id: str) -> Optional["ShellSession"]:
        """
        获取指定 ID 的会话

        Args:
            session_id: 会话 ID

        Returns:
            Optional[ShellSession]: 会话对象或 None
        """
        with self._lock:
            session_info = self._sessions.get(session_id)
            if session_info and session_info.is_active:
                return session_info.shell_session
            return None

    def close_session(self, session_id: str) -> bool:
        """
        关闭指定会话

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否成功关闭
        """
        with self._lock:
            session_info = self._sessions.get(session_id)
            if not session_info:
                logger.warning(f"Session '{session_id}' not found")
                return False

            try:
                session_info.shell_session.close()
                session_info.is_active = False
                logger.info(f"Closed session: {session_id}")
                return True
            except Exception as e:
                logger.error(f"Error closing session {session_id}: {e}")
                return False

    def close_all_sessions(self) -> int:
        """
        关闭所有会话

        Returns:
            int: 关闭的会话数
        """
        with self._lock:
            closed_count = 0
            for session_id, session_info in list(self._sessions.items()):
                if session_info.is_active:
                    try:
                        session_info.shell_session.close()
                        session_info.is_active = False
                        closed_count += 1
                    except Exception as e:
                        logger.error(f"Error closing session {session_id}: {e}")

            logger.info(f"Closed {closed_count} sessions")
            return closed_count

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """
        获取会话详细信息

        Args:
            session_id: 会话 ID

        Returns:
            Optional[Dict]: 会话信息
        """
        with self._lock:
            session_info = self._sessions.get(session_id)
            if not session_info:
                return None

            return {
                "session_id": session_info.session_id,
                "is_active": session_info.is_active,
                "created_at": session_info.created_at,
                "last_used": session_info.last_used,
                "command_count": session_info.command_count,
                "age_seconds": time.time() - session_info.created_at,
                "idle_seconds": time.time() - session_info.last_used,
            }

    def list_sessions(self) -> List[str]:
        """
        列出所有会话 ID

        Returns:
            List[str]: 会话 ID 列表
        """
        with self._lock:
            return [sid for sid, info in self._sessions.items() if info.is_active]

    def get_all_sessions_info(self) -> List[Dict]:
        """
        获取所有会话信息

        Returns:
            List[Dict]: 所有会话信息列表
        """
        with self._lock:
            return [
                {
                    "session_id": info.session_id,
                    "is_active": info.is_active,
                    "created_at": info.created_at,
                    "last_used": info.last_used,
                    "command_count": info.command_count,
                }
                for info in self._sessions.values()
            ]

    @property
    def active_session_count(self) -> int:
        """活跃会话数"""
        with self._lock:
            return sum(1 for info in self._sessions.values() if info.is_active)
