"""
SSH后端抽象基类
定义与具体实现无关的接口
"""

from abc import ABC, abstractmethod
from typing import Protocol, Optional, Any, runtime_checkable
from dataclasses import dataclass

# ============ 协议定义 ============


@runtime_checkable
class Channel(Protocol):
    """通道协议 - 定义通道必须实现的方法"""

    def recv(self, nbytes: int) -> bytes: ...

    def send(self, data: bytes) -> int: ...

    def close(self) -> None: ...

    @property
    def closed(self) -> bool: ...

    def settimeout(self, timeout: Optional[float]) -> None: ...

    def exec_command(self, command: str) -> None: ...

    def get_pty(self, term: str = "vt100", width: int = 80, height: int = 24) -> None: ...

    def invoke_shell(self) -> None: ...

    def get_id(self) -> int: ...

    @property
    def exit_status_ready(self) -> bool: ...

    def recv_exit_status(self) -> int: ...

    def recv_stderr_ready(self) -> bool: ...

    def recv_stderr(self, nbytes: int) -> bytes: ...

    def recv_ready(self) -> bool:
        """检查是否有stdout数据可读"""
        ...

    def setblocking(self, blocking: bool) -> None:
        """设置阻塞模式"""
        ...


@runtime_checkable
class Transport(Protocol):
    """传输层协议"""

    def open_session(self) -> Channel: ...

    def is_active(self) -> bool: ...

    def close(self) -> None: ...


# ============ 数据类 ============


@dataclass
class ConnectionInfo:
    """连接信息"""

    host: str
    port: int
    username: str
    is_connected: bool
    server_version: Optional[str] = None


# ============ 异常定义 ============


class AuthenticationError(Exception):
    """认证错误"""

    pass


import builtins


class ConnectionError(builtins.ConnectionError):
    """连接错误"""

    pass


class SSHException(Exception):
    """SSH通用错误"""

    pass


class ChannelException(Exception):
    """通道错误"""

    pass


# ============ 抽象基类 ============


class SSHBackend(ABC):
    """SSH后端抽象基类"""

    @abstractmethod
    def connect(
        self,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        key_password: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        """建立连接"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass

    @abstractmethod
    def open_channel(self) -> Channel:
        """打开新通道"""
        pass

    @abstractmethod
    def get_transport(self) -> Optional[Transport]:
        """获取传输层"""
        pass

    @abstractmethod
    def get_connection_info(self) -> ConnectionInfo:
        """获取连接信息"""
        pass

    @property
    @abstractmethod
    def raw_client(self) -> Any:
        """获取原始客户端（用于高级操作）"""
        pass
