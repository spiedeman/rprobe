"""
Paramiko SSH后端实现
包装paramiko库，实现抽象接口
"""

import logging
from typing import Optional, Tuple

try:
    import paramiko

    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False

from .base import (
    SSHBackend,
    Channel,
    Transport,
    ConnectionInfo,
    AuthenticationError,
    ConnectionError,
    SSHException,
    ChannelException,
)

logger = logging.getLogger(__name__)

# ============ Paramiko包装器 ============


class ParamikoChannel:
    """Paramiko通道包装器"""

    def __init__(self, channel: "paramiko.Channel"):
        self._channel = channel

    def recv(self, nbytes: int) -> bytes:
        try:
            return self._channel.recv(nbytes)
        except paramiko.SSHException as e:
            raise ChannelException(f"接收数据失败: {e}") from e

    def send(self, data: bytes) -> int:
        try:
            return self._channel.send(data)
        except paramiko.SSHException as e:
            raise ChannelException(f"发送数据失败: {e}") from e

    def close(self) -> None:
        self._channel.close()

    @property
    def closed(self) -> bool:
        return self._channel.closed

    def settimeout(self, timeout: Optional[float]) -> None:
        self._channel.settimeout(timeout)

    def exec_command(self, command: str) -> None:
        self._channel.exec_command(command)

    def get_pty(self, term: str = "vt100", width: int = 80, height: int = 24) -> None:
        self._channel.get_pty(term, width, height)

    def invoke_shell(self) -> None:
        self._channel.invoke_shell()

    def get_id(self) -> int:
        return self._channel.get_id()

    @property
    def exit_status_ready(self) -> bool:
        return self._channel.exit_status_ready()

    def recv_exit_status(self) -> int:
        return self._channel.recv_exit_status()

    def recv_stderr_ready(self) -> bool:
        return self._channel.recv_stderr_ready()

    def recv_stderr(self, nbytes: int) -> bytes:
        return self._channel.recv_stderr(nbytes)

    def recv_ready(self) -> bool:
        """检查是否有stdout数据可读"""
        return self._channel.recv_ready()

    def setblocking(self, blocking: bool) -> None:
        """设置阻塞模式"""
        self._channel.setblocking(blocking)

    @property
    def active(self) -> bool:
        """检查channel是否活跃（未关闭且传输层活跃）"""
        try:
            return self._channel.active
        except Exception:
            # 如果底层调用失败，保守返回False
            return False

    def get_transport(self) -> Optional["ParamikoTransport"]:
        """获取关联的transport对象"""
        underlying_transport = self._channel.get_transport()
        if underlying_transport:
            return ParamikoTransport(underlying_transport)
        return None

    def getpeername(self) -> Optional[tuple]:
        """获取远程地址"""
        try:
            return self._channel.getpeername()
        except Exception:
            return None

    def gettimeout(self) -> Optional[float]:
        """获取超时设置"""
        return self._channel.gettimeout()

    def sendall(self, data: bytes) -> None:
        """确保完整发送数据"""
        try:
            self._channel.sendall(data)
        except paramiko.SSHException as e:
            raise ChannelException(f"发送数据失败: {e}") from e

    def makefile(self, *args, **kwargs):
        """创建文件对象"""
        return self._channel.makefile(*args, **kwargs)

    def resize_pty(self, width: int = 80, height: int = 24) -> None:
        """调整伪终端大小"""
        self._channel.resize_pty(width, height)

    def shutdown(self, how: int) -> None:
        """关闭连接的一部分"""
        self._channel.shutdown(how)


class ParamikoTransport:
    """Paramiko传输层包装器"""

    def __init__(self, transport: "paramiko.Transport"):
        self._transport = transport

    def open_session(self) -> Channel:
        return ParamikoChannel(self._transport.open_session())

    def is_active(self) -> bool:
        return self._transport.is_active()

    def close(self) -> None:
        self._transport.close()

    @property
    def _channels(self):
        """提供对底层_channels的访问（用于兼容性）"""
        return getattr(self._transport, "_channels", {})


# ============ 后端实现 ============


class ParamikoBackend(SSHBackend):
    """Paramiko SSH后端"""

    def __init__(self):
        if not PARAMIKO_AVAILABLE:
            raise ImportError(
                "paramiko is required for ParamikoBackend. "
                "Install with: pip install remotesh[paramiko]"
            )
        self._client: Optional["paramiko.SSHClient"] = None
        self._transport: Optional["paramiko.Transport"] = None
        self._connection_info: Optional[ConnectionInfo] = None
        self._host_key_policy = paramiko.AutoAddPolicy()

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
        """建立SSH连接"""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(self._host_key_policy)

        try:
            connect_kwargs = {
                "hostname": host,
                "port": port,
                "username": username,
                "timeout": timeout,
                "allow_agent": False,
                "look_for_keys": False,
            }

            if password:
                connect_kwargs["password"] = password
                auth_method = "password"
            elif key_filename:
                connect_kwargs["key_filename"] = key_filename
                if key_password:
                    connect_kwargs["passphrase"] = key_password
                auth_method = "key"
            else:
                auth_method = "unknown"

            logger.debug(f"使用 {auth_method} 认证方式")

            self._client.connect(**connect_kwargs)
            self._transport = self._client.get_transport()

            self._connection_info = ConnectionInfo(
                host=host,
                port=port,
                username=username,
                is_connected=True,
                server_version=getattr(self._transport, "remote_version", None),
            )

            logger.info(f"SSH连接成功: {host}:{port}")

        except paramiko.AuthenticationException as e:
            self._cleanup()
            raise AuthenticationError(f"认证失败: {e}") from e
        except paramiko.SSHException as e:
            self._cleanup()
            raise SSHException(f"SSH错误: {e}") from e
        except Exception as e:
            self._cleanup()
            raise ConnectionError(f"连接错误: {e}") from e

    def disconnect(self) -> None:
        """断开连接"""
        self._cleanup()
        if self._connection_info:
            self._connection_info.is_connected = False
        logger.info("SSH连接已断开")

    def _cleanup(self) -> None:
        """清理资源"""
        if self._transport:
            try:
                self._transport.close()
            except Exception as e:
                logger.warning(f"关闭 Transport 时出错: {e}")
            self._transport = None
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(f"关闭 SSHClient 时出错: {e}")
            self._client = None

    def is_connected(self) -> bool:
        return self._transport is not None and self._transport.is_active()

    def open_channel(self) -> Channel:
        if not self.is_connected():
            raise ConnectionError("未连接到SSH服务器")
        try:
            return ParamikoChannel(self._transport.open_session())
        except paramiko.SSHException as e:
            raise ChannelException(f"打开通道失败: {e}") from e

    def get_transport(self) -> Optional[Transport]:
        if self._transport:
            return ParamikoTransport(self._transport)
        return None

    def get_connection_info(self) -> ConnectionInfo:
        if self._connection_info:
            return self._connection_info
        raise ConnectionError("未建立连接")

    @property
    def raw_client(self) -> "paramiko.SSHClient":
        if not self._client:
            raise ConnectionError("未建立连接")
        return self._client
