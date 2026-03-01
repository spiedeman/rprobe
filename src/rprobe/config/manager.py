"""
配置管理模块

提供统一的配置加载、验证和管理功能。
支持从代码、文件（YAML/JSON）、环境变量加载配置。

Features:
- 多源配置加载（代码、文件、环境变量）
- 配置验证和默认值
- 配置层级（优先级）管理
- 类型安全

Example:
    from rprobe.config import SSHConfig, ConfigManager

    # 方式1: 直接从代码创建
    config = SSHConfig(
        host="example.com",
        username="user",
        password="password"
    )

    # 方式2: 从YAML文件加载
    config = ConfigManager.load_from_file("config.yaml")

    # 方式3: 从环境变量加载
    config = ConfigManager.load_from_env()

    # 方式4: 混合加载
    config = ConfigManager()
        .from_file("config.yaml")  # 基础配置
        .from_env()                # 环境变量覆盖
        .build()
"""

import os
import json
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path

from rprobe.exceptions import ConfigurationError

# 尝试导入yaml
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


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
                "密码和密钥不能同时指定，请选择一种认证方式", "password/key_filename"
            )

        if not self.password and not self.key_filename:
            raise ConfigurationError("必须指定密码或密钥文件路径", "password/key_filename")

        if self.port < 1 or self.port > 65535:
            raise ConfigurationError(f"端口号必须在1-65535之间，当前值: {self.port}", "port")

        if self.key_filename and not Path(self.key_filename).exists():
            raise ConfigurationError(f"密钥文件不存在: {self.key_filename}", "key_filename")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SSHConfig":
        """从字典创建配置"""
        # 过滤掉无效字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    def copy_with(self, **kwargs) -> "SSHConfig":
        """创建配置的副本并修改指定字段"""
        data = self.to_dict()
        data.update(kwargs)
        return SSHConfig.from_dict(data)

    def __str__(self) -> str:
        """字符串表示"""
        auth_method = "password" if self.password else "key"
        return f"SSHConfig({self.username}@{self.host}:{self.port}, auth={auth_method})"


class ConfigManager:
    """
    配置管理器

    支持从多种来源加载和合并配置。
    """

    # 环境变量前缀
    ENV_PREFIX = "REMOTE_SSH_"

    # 环境变量映射
    ENV_MAPPING = {
        "HOST": "host",
        "USERNAME": "username",
        "PORT": "port",
        "PASSWORD": "password",
        "KEY_FILENAME": "key_filename",
        "KEY_PASSWORD": "key_password",
        "TIMEOUT": "timeout",
        "COMMAND_TIMEOUT": "command_timeout",
        "MAX_OUTPUT_SIZE": "max_output_size",
        "ENCODING": "encoding",
        "RECV_MODE": "recv_mode",
        "RECV_POLL_INTERVAL": "recv_poll_interval",
    }

    def __init__(self):
        self._data: Dict[str, Any] = {}

    def from_dict(self, data: Dict[str, Any]) -> "ConfigManager":
        """从字典加载配置"""
        self._data.update(data)
        return self

    def from_file(self, path: Union[str, Path]) -> "ConfigManager":
        """
        从文件加载配置

        支持YAML和JSON格式。

        Args:
            path: 配置文件路径

        Returns:
            ConfigManager: self

        Raises:
            ConfigurationError: 文件不存在或格式错误
        """
        path = Path(path)

        if not path.exists():
            raise ConfigurationError(f"配置文件不存在: {path}", "config_file")

        try:
            content = path.read_text(encoding="utf-8")

            if path.suffix in (".yaml", ".yml"):
                if not YAML_AVAILABLE:
                    raise ConfigurationError(
                        "YAML support not available. Install PyYAML: pip install pyyaml", "yaml"
                    )
                data = yaml.safe_load(content)
            elif path.suffix == ".json":
                data = json.loads(content)
            else:
                raise ConfigurationError(
                    f"不支持的配置文件格式: {path.suffix}. 请使用 .yaml, .yml 或 .json",
                    "config_file",
                )

            self._data.update(data)
            return self

        except Exception as e:
            raise ConfigurationError(f"加载配置文件失败: {e}", "config_file")

    def from_env(self, prefix: Optional[str] = None) -> "ConfigManager":
        """
        从环境变量加载配置

        Args:
            prefix: 环境变量前缀，默认REMOTE_SSH_

        Returns:
            ConfigManager: self
        """
        prefix = prefix or self.ENV_PREFIX

        for env_key, config_key in self.ENV_MAPPING.items():
            full_key = f"{prefix}{env_key}"
            value = os.getenv(full_key)

            if value is not None:
                # 类型转换
                if config_key in ("port", "max_output_size"):
                    value = int(value)
                elif config_key in ("timeout", "command_timeout", "recv_poll_interval"):
                    value = float(value)
                elif config_key == "recv_mode":
                    value = value.lower()

                self._data[config_key] = value

        return self

    def set(self, key: str, value: Any) -> "ConfigManager":
        """设置单个配置项"""
        self._data[key] = value
        return self

    def build(self) -> SSHConfig:
        """
        构建SSHConfig对象

        Returns:
            SSHConfig: 配置对象
        """
        return SSHConfig.from_dict(self._data)

    @classmethod
    def load_from_file(cls, path: Union[str, Path]) -> SSHConfig:
        """便捷方法：从文件加载配置"""
        return cls().from_file(path).build()

    @classmethod
    def load_from_env(cls, prefix: Optional[str] = None) -> SSHConfig:
        """便捷方法：从环境变量加载配置"""
        return cls().from_env(prefix).build()

    @classmethod
    def create_default(cls, host: str, username: str, **kwargs) -> SSHConfig:
        """
        创建默认配置

        Args:
            host: 主机地址
            username: 用户名
            **kwargs: 其他配置参数

        Returns:
            SSHConfig: 配置对象
        """
        return SSHConfig(host=host, username=username, **kwargs)


# 便捷函数
def load_config(file_path: Optional[str] = None, use_env: bool = True, **kwargs) -> SSHConfig:
    """
    加载配置

    加载优先级（从高到低）：
    1. 代码中直接传入的参数（kwargs）
    2. 环境变量
    3. 配置文件
    4. 默认值

    Args:
        file_path: 配置文件路径
        use_env: 是否从环境变量加载
        **kwargs: 代码中直接传入的配置

    Returns:
        SSHConfig: 配置对象
    """
    manager = ConfigManager()

    # 1. 加载配置文件
    if file_path:
        manager.from_file(file_path)

    # 2. 加载环境变量（覆盖配置文件）
    if use_env:
        manager.from_env()

    # 3. 代码参数覆盖（最高优先级）
    if kwargs:
        manager.from_dict(kwargs)

    return manager.build()
