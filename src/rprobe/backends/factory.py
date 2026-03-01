"""
SSH后端工厂
管理后端注册和创建
"""

import logging
from typing import Type, Dict, Optional
from .base import SSHBackend

logger = logging.getLogger(__name__)


class BackendFactory:
    """SSH后端工厂"""

    _backends: Dict[str, Type[SSHBackend]] = {}
    _default_backend: Optional[str] = None

    @classmethod
    def register(cls, name: str, backend_class: Type[SSHBackend], default: bool = False) -> None:
        """注册后端"""
        cls._backends[name] = backend_class
        if default or cls._default_backend is None:
            cls._default_backend = name
        logger.debug(f"注册后端: {name}")

    @classmethod
    def create(cls, name: Optional[str] = None) -> SSHBackend:
        """创建后端实例"""
        backend_name = name or cls._default_backend
        if backend_name not in cls._backends:
            raise ValueError(
                f"未知后端: {backend_name}. " f"可用后端: {list(cls._backends.keys())}"
            )
        return cls._backends[backend_name]()

    @classmethod
    def list_backends(cls) -> list:
        """列出可用后端"""
        return list(cls._backends.keys())

    @classmethod
    def get_default_backend(cls) -> Optional[str]:
        """获取默认后端名称"""
        return cls._default_backend

    @classmethod
    def is_backend_available(cls, name: str) -> bool:
        """检查后端是否可用"""
        return name in cls._backends


# 自动注册paramiko后端
try:
    from .paramiko_backend import ParamikoBackend

    BackendFactory.register("paramiko", ParamikoBackend, default=True)
    logger.debug("Paramiko后端已自动注册")
except ImportError:
    logger.warning("paramiko后端不可用，未注册")
