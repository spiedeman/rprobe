"""
工具函数模块

提供各种实用的工具函数。
"""

import re
import time
import functools
from typing import Any, Callable, Optional, TypeVar, cast

T = TypeVar("T")


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 延迟增长倍数
        exceptions: 需要重试的异常类型

    Example:
        @retry(max_attempts=3, delay=1.0)
        def connect_to_server():
            # 连接逻辑
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            attempt = 1
            current_delay = delay

            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        raise

                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1

            # 不应该执行到这里
            raise RuntimeError("Unexpected end of retry loop")

        return wrapper

    return decorator


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """
    清理字符串，移除控制字符

    Args:
        text: 原始字符串
        max_length: 最大长度

    Returns:
        str: 清理后的字符串
    """
    # 移除控制字符
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 截断过长字符串
    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text


def truncate_middle(text: str, max_length: int = 100, ellipsis: str = "...") -> str:
    """
    截断字符串中间部分

    Args:
        text: 原始字符串
        max_length: 最大长度
        ellipsis: 省略符号

    Returns:
        str: 截断后的字符串
    """
    if len(text) <= max_length:
        return text

    ellipsis_len = len(ellipsis)
    part_len = (max_length - ellipsis_len) // 2

    return text[:part_len] + ellipsis + text[-part_len:]


def format_bytes(size: int) -> str:
    """
    格式化字节大小

    Args:
        size: 字节数

    Returns:
        str: 格式化后的字符串
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def format_duration(seconds: float) -> str:
    """
    格式化持续时间

    Args:
        seconds: 秒数

    Returns:
        str: 格式化后的字符串
    """
    if seconds < 0.001:
        return f"{seconds * 1000000:.2f} µs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    elif seconds < 60:
        return f"{seconds:.2f} s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def deep_merge(base: dict, override: dict) -> dict:
    """
    深度合并两个字典

    Args:
        base: 基础字典
        override: 覆盖字典

    Returns:
        dict: 合并后的字典
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def safe_get(dictionary: dict, key: str, default: Any = None) -> Any:
    """
    安全获取字典值

    Args:
        dictionary: 字典
        key: 键
        default: 默认值

    Returns:
        Any: 值或默认值
    """
    return dictionary.get(key, default)


class Timer:
    """
    计时器上下文管理器

    Example:
        with Timer() as timer:
            # 执行某些操作
            time.sleep(1)

        print(f"耗时: {timer.elapsed:.2f}秒")
    """

    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def __enter__(self) -> "Timer":
        self.start_time = time.time()
        return self

    def __exit__(self, *args) -> None:
        self.end_time = time.time()

    @property
    def elapsed(self) -> float:
        """获取经过的时间"""
        if self.end_time is not None:
            return self.end_time - self.start_time
        elif self.start_time is not None:
            return time.time() - self.start_time
        return 0.0

    def __str__(self) -> str:
        return format_duration(self.elapsed)


class Singleton:
    """
    单例模式基类

    Example:
        class MyClass(Singleton):
            def __init__(self):
                self.value = 42

        a = MyClass()
        b = MyClass()
        assert a is b
    """

    _instances: dict = {}

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]
