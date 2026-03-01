"""
连接工厂模块

提供统一的 SSH Channel 创建和管理，消除重复代码。
支持多种 Channel 类型：exec、shell、sftp 等。
使用上下文管理器确保资源正确释放。
"""

import logging
from contextlib import contextmanager
from typing import Optional, Union, Generator, TYPE_CHECKING

if TYPE_CHECKING:
    from rprobe.backends.base import Channel, Transport
    from rprobe.core.connection import ConnectionManager
    from rprobe.pooling import ConnectionPool


logger = logging.getLogger(__name__)


class ConnectionFactory:
    """
    SSH Channel 创建工厂

    统一封装 Channel 创建逻辑，消除代码重复。
    支持连接池和直接连接两种模式。

    Example:
        # 创建 exec channel
        with ConnectionFactory.create_exec_channel(
            pool=connection_pool,
            use_pool=True,
            command="ls -la",
            timeout=60.0
        ) as channel:
            # 使用 channel...
            pass  # 自动关闭
    """

    @staticmethod
    @contextmanager
    def create_exec_channel(
        connection_source: Optional[Union["ConnectionManager", "ConnectionPool"]] = None,
        use_pool: bool = False,
        command: str = "",
        timeout: float = 60.0,
        transport: Optional["Transport"] = None,
    ) -> Generator["Channel", None, None]:
        """
        创建 exec 类型的 Channel（上下文管理器）

        统一封装以下重复逻辑：
        1. 获取连接（池或直连）
        2. transport.open_session()
        3. channel.settimeout()
        4. channel.exec_command()
        5. 自动关闭 channel

        Args:
            connection_source: 连接源（ConnectionManager 或 ConnectionPool）
            use_pool: 是否使用连接池
            command: 要执行的命令
            timeout: 超时时间（秒）
            transport: 可选的直接传入 transport（优先级最高）

        Yields:
            Channel: 配置好的 exec channel

        Example:
            with ConnectionFactory.create_exec_channel(
                pool=my_pool, use_pool=True, command="ls", timeout=30.0
            ) as channel:
                stdout = channel.recv(1024)
        """
        channel = None
        connection_context = None

        try:
            # 获取 transport
            if transport is not None:
                # 直接使用传入的 transport
                pass
            elif use_pool and connection_source is not None:
                # 从连接池获取
                connection_context = connection_source.get_connection()
                conn = connection_context.__enter__()
                transport = conn.transport
            elif not use_pool and connection_source is not None:
                # 直接连接模式
                connection_source.ensure_connected()
                transport = connection_source.transport
            else:
                raise ValueError("必须提供 transport 或 connection_source")

            # 创建 channel
            channel = transport.open_session()
            channel.settimeout(timeout)
            channel.exec_command(command)

            logger.debug(f"Created exec channel for command: {command[:50]}...")
            yield channel

        except Exception as e:
            logger.error(f"Failed to create exec channel: {e}")
            raise
        finally:
            # 清理资源
            if channel:
                try:
                    channel.close()
                    logger.debug("Exec channel closed")
                except Exception as e:
                    logger.warning(f"Error closing channel: {e}")

            # 如果是连接池模式，确保连接上下文正确退出
            if connection_context is not None:
                try:
                    connection_context.__exit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error releasing connection: {e}")

    @staticmethod
    @contextmanager
    def create_shell_channel(
        connection_source: Optional[Union["ConnectionManager", "ConnectionPool"]] = None,
        use_pool: bool = False,
        timeout: float = 60.0,
        transport: Optional["Transport"] = None,
    ) -> Generator["Channel", None, None]:
        """
        创建 shell 类型的 Channel（上下文管理器）

        用于交互式 shell 会话。

        Args:
            connection_source: 连接源
            use_pool: 是否使用连接池
            timeout: 超时时间
            transport: 可选的直接传入 transport

        Yields:
            Channel: 配置好的 shell channel
        """
        channel = None
        connection_context = None

        try:
            # 获取 transport
            if transport is not None:
                pass
            elif use_pool and connection_source is not None:
                connection_context = connection_source.get_connection()
                conn = connection_context.__enter__()
                transport = conn.transport
            elif not use_pool and connection_source is not None:
                connection_source.ensure_connected()
                transport = connection_source.transport
            else:
                raise ValueError("必须提供 transport 或 connection_source")

            # 创建 shell channel
            channel = transport.open_session()
            channel.settimeout(timeout)
            channel.get_pty()
            channel.invoke_shell()

            logger.debug("Created shell channel")
            yield channel

        except Exception as e:
            logger.error(f"Failed to create shell channel: {e}")
            raise
        finally:
            if channel:
                try:
                    channel.close()
                    logger.debug("Shell channel closed")
                except Exception as e:
                    logger.warning(f"Error closing channel: {e}")

            if connection_context is not None:
                try:
                    connection_context.__exit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error releasing connection: {e}")

    @staticmethod
    def create_channel_simple(
        transport: "Transport",
        channel_type: str = "exec",
        command: str = "",
        timeout: float = 60.0,
    ) -> "Channel":
        """
        简单创建 Channel（非上下文管理器版本）

        适用于调用方需要自己管理生命周期的场景。

        Args:
            transport: SSH transport
            channel_type: channel 类型 ('exec' 或 'shell')
            command: 命令（仅 exec 类型需要）
            timeout: 超时时间

        Returns:
            Channel: 配置好的 channel（调用方负责关闭）
        """
        channel = transport.open_session()
        channel.settimeout(timeout)

        if channel_type == "exec":
            channel.exec_command(command)
        elif channel_type == "shell":
            channel.get_pty()
            channel.invoke_shell()
        else:
            raise ValueError(f"Unknown channel type: {channel_type}")

        return channel
