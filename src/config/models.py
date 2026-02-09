"""
配置模型模块

提供SSH配置相关的数据模型。
"""
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional
from pathlib import Path

from src.exceptions import ConfigurationError


class RecvMode(Enum):
    """数据接收模式"""
    AUTO = "auto"           # 自动选择
    SELECT = "select"       # Select模式（Linux/Mac）
    ADAPTIVE = "adaptive"   # 自适应轮询
    ORIGINAL = "original"   # 原始轮询


@dataclass
class SSHConfig:
    """
    SSH连接配置
    
    Attributes:
        host: 远程主机地址
        username: 用户名
        port: SSH端口（默认22）
        password: 密码（可选，与key_filename二选一）
        key_filename: 私钥文件路径（可选）
        key_password: 私钥密码（可选）
        timeout: 连接超时时间（秒，默认30）
        command_timeout: 命令执行超时（秒，默认300）
        max_output_size: 最大输出大小（字节，默认10MB）
        encoding: 输出编码（默认utf-8）
        recv_mode: 数据接收模式（默认auto）
        recv_poll_interval: 轮询间隔（秒，仅用于original模式）
    """
    
    host: str
    username: str
    port: int = 22
    password: Optional[str] = None
    key_filename: Optional[str] = None
    key_password: Optional[str] = None
    timeout: float = 30.0
    command_timeout: float = 300.0
    max_output_size: int = 10 * 1024 * 1024  # 10MB
    encoding: str = "utf-8"
    recv_mode: str = "auto"
    recv_poll_interval: float = 0.001  # 1ms
    
    def __post_init__(self):
        """验证配置有效性"""
        self.validate()
    
    def validate(self) -> None:
        """
        验证配置
        
        Raises:
            ConfigurationError: 配置无效
        """
        if not self.host:
            raise ConfigurationError("主机地址不能为空", "host")
        
        if not self.username:
            raise ConfigurationError("用户名不能为空", "username")
        
        if self.password and self.key_filename:
            raise ConfigurationError(
                "密码和密钥不能同时指定，请选择一种认证方式",
                "password/key_filename"
            )
        
        if not self.password and not self.key_filename:
            raise ConfigurationError(
                "必须指定密码或密钥文件路径",
                "password/key_filename"
            )
        
        if self.port < 1 or self.port > 65535:
            raise ConfigurationError(
                f"端口号必须在1-65535之间，当前值: {self.port}",
                "port"
            )
        
        # 只在非测试环境下检查密钥文件存在性
        import os
        if self.key_filename and not os.environ.get('TESTING'):
            if not Path(self.key_filename).exists():
                raise ConfigurationError(
                    f"密钥文件不存在: {self.key_filename}",
                    "key_filename"
                )
    
    def to_dict(self):
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建配置"""
        # 过滤掉无效字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    def copy_with(self, **kwargs):
        """创建配置的副本并修改指定字段"""
        data = self.to_dict()
        data.update(kwargs)
        return SSHConfig.from_dict(data)
    
    def __str__(self) -> str:
        """字符串表示"""
        auth_method = "password" if self.password else "key"
        return f"SSHConfig({self.username}@{self.host}:{self.port}, auth={auth_method})"
