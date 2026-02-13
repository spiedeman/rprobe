"""
RemoteSSH - 高级SSH客户端库

提供高性能、可扩展的SSH连接和命令执行功能。

Features:
- 连接池管理：复用连接，减少开销
- 结构化日志：JSON格式，便于分析
- 多源配置：支持代码、文件、环境变量
- 性能优化：多种数据接收模式
- 交互式支持：scapy, ipython等动态提示符

Example:
    from remotessh import SSHClient, load_config
    
    # 加载配置
    config = load_config(file_path="config.yaml")
    
    # 使用连接池
    with SSHClient(config, use_pool=True) as client:
        result = client.exec_command("ls -la")
        print(result.stdout)
"""

__version__ = "1.0.0"
__author__ = "RemoteSSH Team"

# 配置管理
from src.config import SSHConfig, ConfigManager, load_config

# 核心组件
from src.core import SSHClient, ConnectionManager, MultiSessionManager, SessionInfo, CommandResult

# 会话管理
from src.session import ShellSession

# 提示符模式
from src.patterns import PromptDetector, PromptPattern, PromptPatternBuilder, PromptCategory

# 数据接收器
from src.receivers import (
    SmartChannelReceiver,
    create_receiver
)

# 连接池
from src.pooling import ConnectionPool, get_pool_manager

# 异常
from src.exceptions import (
    SSHError,
    ConnectionError,
    AuthenticationError,
    CommandTimeoutError,
    CommandExecutionError,
    ConfigurationError,
    PoolError
)

# 日志
from src.logging_config import configure_logging, get_logger

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
