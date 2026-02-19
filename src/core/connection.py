"""
SSH 连接管理模块
提供 SSH 连接的生命周期管理
"""
import logging
import threading
import time
from typing import Optional, List, Dict, TYPE_CHECKING, Any
from dataclasses import dataclass, field

# 移除：import paramiko
# 改为从后端导入
from src.backends import (
    SSHBackend,
    Channel,
    AuthenticationError,
    SSHException,
    ConnectionError,
    BackendFactory,
)
from src.config.models import SSHConfig

if TYPE_CHECKING:
    from src.session.shell_session import ShellSession

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    SSH 连接管理器

    使用可插拔的SSH后端实现连接管理
    """

    def __init__(self, config: SSHConfig, backend: Optional[SSHBackend] = None):
        """
        初始化连接管理器

        Args:
            config: SSH 连接配置
            backend: SSH后端实例（可选，默认使用工厂创建）
        """
        self._config = config
        # 使用传入的后端或从工厂创建
        self._backend = backend or BackendFactory.create()
        logger.debug(
            f"ConnectionManager初始化完成，使用后端: {type(self._backend).__name__}"
        )

    @property
    def is_connected(self) -> bool:
        """检查连接是否活跃"""
        return self._backend.is_connected()

    @property
    def transport(self):
        """获取传输层对象"""
        return self._backend.get_transport()

    def connect(self) -> None:
        """
        建立 SSH 连接

        Raises:
            AuthenticationError: 认证失败
            SSHException: SSH 连接错误
            ConnectionError: 连接错误
        """
        if self.is_connected:
            logger.debug(f"SSH 连接已存在: {self._config.host}")
            return

        logger.info(f"正在连接 SSH 服务器: {self._config.host}:{self._config.port}")

        try:
            self._backend.connect(
                host=self._config.host,
                port=self._config.port,
                username=self._config.username,
                password=self._config.password,
                key_filename=self._config.key_filename,
                key_password=self._config.key_password,
                timeout=self._config.timeout,
            )
            logger.info(f"SSH 连接成功: {self._config.host}")

        except AuthenticationError:
            logger.error(f"SSH 认证失败: {self._config.host}")
            raise
        except SSHException as e:
            logger.error(f"SSH 连接错误: {self._config.host} - {e}")
            raise
        except ConnectionError as e:
            logger.error(f"SSH 连接异常: {self._config.host} - {e}")
            raise
        except Exception as e:
            logger.error(f"SSH 连接异常: {self._config.host} - {e}")
            raise ConnectionError(f"连接失败: {e}") from e

    def disconnect(self) -> None:
        """断开 SSH 连接"""
        if not self.is_connected:
            return

        logger.info(f"正在断开 SSH 连接: {self._config.host}")
        self._backend.disconnect()
        logger.info(f"SSH 连接已断开: {self._config.host}")

    def open_channel(self, timeout: Optional[float] = None) -> Channel:
        """
        打开新的 SSH 通道

        Args:
            timeout: 超时时间

        Returns:
            Channel: 新打开的通道
        """
        self.ensure_connected()
        channel = self._backend.open_channel()
        if timeout:
            channel.settimeout(timeout)
        return channel

    def open_shell_session(self, timeout: Optional[float] = None) -> Channel:
        """
        打开新的 Shell 会话通道

        一个 SSH 连接可以打开多个独立的 Shell 会话，
        每个会话都有自己的 channel 和状态。

        Args:
            timeout: 超时时间

        Returns:
            Channel: 配置好的 Shell 会话通道
        """
        self.ensure_connected()
        channel = self._backend.open_channel()
        channel.get_pty()
        channel.invoke_shell()
        if timeout:
            channel.settimeout(timeout)
        logger.debug(f"Opened new shell session channel")
        return channel

    def get_active_channels_count(self) -> int:
        """
        获取当前活跃的通道数量

        Returns:
            int: 活跃通道数
        """
        if not self.is_connected:
            return 0
        # 通过传输层获取通道数（兼容性处理）
        transport = self._backend.get_transport()
        if transport and hasattr(transport, "_channels"):
            return len(transport._channels)
        return 0

    def ensure_connected(self) -> None:
        """确保连接已建立，如未连接则自动连接"""
        if not self.is_connected:
            logger.debug("连接未建立，自动连接中...")
            self.connect()

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
    channel: Channel  # 改为抽象Channel类型
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

    管理多个独立的 Shell 会话，支持单个连接或连接池模式。
    每个会话都有自己的 channel 和状态，完全独立。
    """

    def __init__(
        self,
        connection: Optional[ConnectionManager] = None,
        config: Optional[SSHConfig] = None,
        use_pool: bool = False,
        pool: Optional[Any] = None,
    ):
        """
        初始化多会话管理器

        Args:
            connection: SSH 连接管理器（直连模式必需）
            config: SSH 配置
            use_pool: 是否使用连接池模式
            pool: 连接池实例（连接池模式必需）

        Raises:
            ValueError: 参数配置无效
        """
        if use_pool and pool is None:
            raise ValueError("使用连接池模式时必须提供 pool 参数")
        if not use_pool and connection is None:
            raise ValueError("直连模式时必须提供 connection 参数")

        self._connection = connection
        self._config = config
        self._use_pool = use_pool
        self._pool = pool
        self._sessions: Dict[str, SessionInfo] = {}
        self._lock = threading.RLock()
        self._session_counter = 0
        self._default_session_id: Optional[str] = None

    def create_session(
        self,
        session_id: Optional[str] = None,
        timeout: Optional[float] = None,
        set_as_default: bool = False,
    ) -> "ShellSession":
        """
        创建新的 Shell 会话

        Args:
            session_id: 会话 ID（可选，自动生成）
            timeout: 初始化超时时间
            set_as_default: 是否设为默认会话

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

            # 根据模式获取 channel
            if self._use_pool:
                # 连接池模式
                channel = self._create_channel_from_pool(timeout)
            else:
                # 直连模式
                channel = self._connection.open_channel(timeout)

            # 创建 ShellSession
            if self._config is None:
                raise RuntimeError("Config is required to create session")
            shell_session = ShellSession(channel, self._config)
            shell_session.initialize(timeout)

            # 保存会话信息
            session_info = SessionInfo(
                session_id=session_id, shell_session=shell_session, channel=channel
            )
            self._sessions[session_id] = session_info

            # 设置默认会话
            if set_as_default or self._default_session_id is None:
                self._default_session_id = session_id

            logger.info(f"Created shell session: {session_id}")
            return shell_session

    def _create_channel_from_pool(self, timeout: Optional[float] = None) -> Channel:
        """从连接池创建 channel"""
        if self._pool is None:
            raise RuntimeError("Connection pool is not available")

        conn = self._pool.get_connection()
        try:
            channel = conn.open_channel(timeout)
            return channel
        except Exception:
            # 如果创建失败，确保连接被正确释放
            conn.close()
            raise

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

                # 更新默认会话
                self._update_default_session(session_id)

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

            # 清除默认会话
            if closed_count > 0:
                self._default_session_id = None

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

    # ========== 默认会话管理 ==========

    def set_default_session(self, session_id: str) -> None:
        """
        设置默认会话

        Args:
            session_id: 会话 ID

        Raises:
            ValueError: 会话不存在或未激活
        """
        with self._lock:
            session_info = self._sessions.get(session_id)
            if not session_info:
                raise ValueError(f"Session '{session_id}' does not exist")
            if not session_info.is_active:
                raise ValueError(f"Session '{session_id}' is not active")

            self._default_session_id = session_id
            logger.debug(f"Set default session: {session_id}")

    def get_default_session(self) -> Optional["ShellSession"]:
        """
        获取默认会话

        Returns:
            Optional[ShellSession]: 默认会话对象，如果没有则返回 None
        """
        with self._lock:
            if self._default_session_id is None:
                return None

            session_info = self._sessions.get(self._default_session_id)
            if not session_info or not session_info.is_active:
                self._default_session_id = None
                return None

            return session_info.shell_session

    def get_default_session_id(self) -> Optional[str]:
        """
        获取默认会话 ID

        Returns:
            Optional[str]: 默认会话 ID
        """
        return self._default_session_id

    def clear_default_session(self) -> None:
        """清除默认会话设置"""
        with self._lock:
            self._default_session_id = None

    def _update_default_session(self, closed_session_id: str) -> None:
        """
        当会话关闭时更新默认会话

        Args:
            closed_session_id: 被关闭的会话 ID
        """
        with self._lock:
            if self._default_session_id == closed_session_id:
                # 查找其他活跃的会话作为新的默认
                for sid, info in self._sessions.items():
                    if info.is_active and sid != closed_session_id:
                        self._default_session_id = sid
                        logger.debug(f"Updated default session to: {sid}")
                        return

                # 没有其他活跃会话
                self._default_session_id = None
