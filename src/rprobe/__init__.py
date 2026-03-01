"""
rprobe - 轻量级远程SSH探针工具

用于快速手动测试和远程设备探查，提供灵活的SSH连接和命令执行功能。

Features:
- 快速探查：轻量级SSH连接
- 结构化输出：支持多种格式转换（Markdown、CSV、JSON）
- 多会话管理：同时管理多个Shell会话
- 模式提取：DSL方式从输出中提取数据

Example:
    from rprobe import SSHClient, load_config

    # 加载配置
    config = load_config(file_path="config.yaml")

    # 快速探查DPU
    with SSHClient(config) as client:
        result = client.shell_command("ifconfig eth0")
        mac = result.match(ifconfig.mac)
        print(mac)
"""

__version__ = "1.0.0"
__author__ = "rprobe Team"

# 配置管理
from rprobe.config import SSHConfig, ConfigManager, load_config

# 核心组件
from rprobe.core import SSHClient, ConnectionManager, MultiSessionManager, SessionInfo, CommandResult

# 会话管理
from rprobe.session import ShellSession

# 提示符模式
from rprobe.patterns import PromptDetector, PromptPattern, PromptPatternBuilder, PromptCategory

# 数据接收器
from rprobe.receivers import SmartChannelReceiver, create_receiver

# 连接池
from rprobe.pooling import ConnectionPool, get_pool_manager

# 异常
from rprobe.exceptions import (
    SSHError,
    ConnectionError,
    AuthenticationError,
    CommandTimeoutError,
    CommandExecutionError,
    ConfigurationError,
    PoolError,
)

# 日志
from rprobe.logging_config import configure_logging, get_logger

__all__ = [
    # 版本
    "__version__",
    # 配置
    "SSHConfig",
    "ConfigManager",
    "load_config",
    # 核心
    "SSHClient",
    "ConnectionManager",
    "MultiSessionManager",
    "SessionInfo",
    "CommandResult",
    # 会话
    "ShellSession",
    # 提示符
    "PromptDetector",
    "PromptPattern",
    "PromptPatternBuilder",
    "PromptCategory",
    # 接收器
    "SmartChannelReceiver",
    "create_receiver",
    # 连接池
    "ConnectionPool",
    "get_pool_manager",
    # 异常
    "SSHError",
    "ConnectionError",
    "AuthenticationError",
    "CommandTimeoutError",
    "CommandExecutionError",
    "ConfigurationError",
    "PoolError",
    # 日志
    "configure_logging",
    "get_logger",
]
