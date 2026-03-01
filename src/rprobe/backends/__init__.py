"""
SSH后端模块
提供SSH实现的抽象层
"""

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

from .factory import BackendFactory

__all__ = [
    "SSHBackend",
    "Channel",
    "Transport",
    "ConnectionInfo",
    "AuthenticationError",
    "ConnectionError",
    "SSHException",
    "ChannelException",
    "BackendFactory",
]
