"""
结构化日志配置模块

提供统一的结构化日志配置，支持JSON格式输出，便于日志聚合和分析。

Features:
- 结构化日志输出（JSON格式）
- 多级日志支持（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- 上下文信息自动注入
- 支持日志轮转
- 支持多个输出目标（控制台、文件、网络）

Example:
    from src.logging_config import get_logger, configure_logging

    # 配置日志
    configure_logging(
        level="INFO",
        format="json",
        output_file="/var/log/remotessh/app.log"
    )

    # 获取logger
    logger = get_logger(__name__)

    # 使用结构化日志
    logger.info(
        "command_executed",
        command="ls -la",
        duration_ms=150,
        exit_code=0,
        host="example.com"
    )
"""

import json
import logging
import logging.handlers
import sys
from typing import Optional, Dict, Any, Union
from pathlib import Path
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """JSON格式的日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        """将日志记录格式化为JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加额外的上下文信息
        if hasattr(record, "context"):
            log_data["context"] = record.context

        # 添加自定义字段
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "asctime",
                "context",
            }:
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""

    COLORS = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
        "RESET": "\033[0m",  # 重置
    }

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录，添加颜色"""
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        formatted = super().format(record)
        return f"{color}{formatted}{reset}"


class StructuredLogger(logging.Logger):
    """结构化日志记录器，支持上下文绑定"""

    def __init__(self, name: str, level: int = logging.NOTSET):
        super().__init__(name, level)
        self._context: Dict[str, Any] = {}

    def bind(self, **kwargs) -> "StructuredLogger":
        """绑定上下文信息"""
        new_logger = self.__class__(self.name, self.level)
        new_logger._context = {**self._context, **kwargs}
        new_logger.handlers = self.handlers
        new_logger.filters = self.filters
        return new_logger

    def unbind(self, *keys) -> "StructuredLogger":
        """解绑上下文信息"""
        new_logger = self.__class__(self.name, self.level)
        new_logger._context = {k: v for k, v in self._context.items() if k not in keys}
        new_logger.handlers = self.handlers
        new_logger.filters = self.filters
        return new_logger

    def _log_with_context(
        self, level: int, msg: str, args: tuple, kwargs: dict
    ) -> None:
        """记录带上下文的日志"""
        # 合并上下文到extra
        extra = kwargs.get("extra", {})
        extra["context"] = self._context

        # 将所有额外的kwargs作为自定义字段
        for key, value in kwargs.items():
            if key != "extra":
                extra[key] = value

        # 只传递extra给_log，不传递其他自定义kwargs
        self._log(level, msg, args, extra=extra)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log_with_context(logging.DEBUG, msg, args, kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._log_with_context(logging.INFO, msg, args, kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log_with_context(logging.WARNING, msg, args, kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._log_with_context(logging.ERROR, msg, args, kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self._log_with_context(logging.CRITICAL, msg, args, kwargs)


# 注册自定义Logger类
logging.setLoggerClass(StructuredLogger)


def configure_logging(
    level: Union[str, int] = "INFO",
    format: str = "colored",
    output_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_console: bool = True,
    enable_file: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    配置日志系统

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: 日志格式 (simple, colored, json)
        output_file: 日志文件路径
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的备份文件数量
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
        context: 全局上下文信息
    """
    # 转换日志级别
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # 创建logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除现有的handlers
    root_logger.handlers.clear()

    # 配置格式
    if format == "json":
        formatter = JSONFormatter()
    elif format == "colored":
        formatter = ColoredFormatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:  # simple
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # 添加控制台处理器
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 添加文件处理器
    if enable_file and output_file:
        log_path = Path(output_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            output_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(level)
        # 文件总是使用JSON格式
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # 设置全局上下文
    if context:
        root_logger = logging.getLogger()
        if isinstance(root_logger, StructuredLogger):
            root_logger._context = context

    logging.info(f"Logging configured, level={level}, format={format}")


def get_logger(name: str) -> StructuredLogger:
    """
    获取结构化日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        StructuredLogger: 结构化日志记录器
    """
    return logging.getLogger(name)


# 便捷的日志函数
logger = get_logger("remotessh")


def log_command_execution(
    command: str,
    host: str,
    duration_ms: float,
    exit_code: int,
    stdout_size: int = 0,
    stderr_size: int = 0,
    **kwargs,
) -> None:
    """
    记录命令执行日志

    Args:
        command: 执行的命令
        host: 目标主机
        duration_ms: 执行时长（毫秒）
        exit_code: 退出码
        stdout_size: 标准输出大小
        stderr_size: 标准错误大小
        **kwargs: 其他上下文信息
    """
    message = f"Command executed: {command} on {host}, duration={duration_ms:.2f}ms, exit_code={exit_code}"

    if exit_code == 0:
        logger.info(message)
    else:
        logger.error(message)


def log_connection_event(
    event: str, host: str, port: int = 22, username: str = "", **kwargs
) -> None:
    """
    记录连接事件日志

    Args:
        event: 事件类型 (connected, disconnected, failed)
        host: 目标主机
        port: 端口
        username: 用户名
        **kwargs: 其他上下文信息
    """
    message = f"Connection {event}: {username}@{host}:{port}"

    if event == "failed":
        logger.error(message)
    elif event == "disconnected":
        logger.info(message)
    else:
        logger.info(message)
