"""
异常映射模块

提供统一的异常映射策略，将后端特定异常映射到项目自定义异常。
确保不同后端抛出一致的异常类型。
"""

import logging
from typing import Type, Dict, Callable, Optional

logger = logging.getLogger(__name__)


class ExceptionMapper:
    """
    统一异常映射器
    
    将后端特定异常（如 paramiko.SSHException）
    映射到项目自定义异常（如 rprobe.backends.base.SSHException）
    
    支持基于异常类型的映射和基于错误消息的映射。
    """
    
    def __init__(self):
        self._mappings: Dict[Type[Exception], Callable[[Exception], Exception]] = {}
        self._message_mappings: Dict[str, Callable[[Exception], Exception]] = {}
    
    def register(self, 
                 source_exc: Type[Exception], 
                 target_factory: Callable[[Exception], Exception]):
        """
        注册异常映射
        
        Args:
            source_exc: 源异常类型
            target_factory: 目标异常工厂函数
        """
        self._mappings[source_exc] = target_factory
        logger.debug(f"注册异常映射: {source_exc.__name__}")
    
    def register_by_message(self,
                           keyword: str,
                           target_factory: Callable[[Exception], Exception]):
        """
        基于错误消息关键词注册映射
        
        Args:
            keyword: 错误消息关键词
            target_factory: 目标异常工厂函数
        """
        self._message_mappings[keyword.lower()] = target_factory
        logger.debug(f"注册消息映射: {keyword}")
    
    def map(self, exc: Exception) -> Exception:
        """
        映射异常
        
        Args:
            exc: 原始异常
            
        Returns:
            映射后的异常
        """
        exc_type = type(exc)
        
        # 1. 先尝试基于类型的映射
        if exc_type in self._mappings:
            return self._mappings[exc_type](exc)
        
        # 2. 尝试基于父类的映射
        for source_type, factory in self._mappings.items():
            if isinstance(exc, source_type):
                return factory(exc)
        
        # 3. 尝试基于消息内容的映射
        error_msg = str(exc).lower()
        for keyword, factory in self._message_mappings.items():
            if keyword in error_msg:
                return factory(exc)
        
        # 4. 没有匹配，返回原异常
        logger.debug(f"没有映射规则 for {exc_type.__name__}: {exc}")
        return exc
    
    def __call__(self, exc: Exception) -> Exception:
        """使实例可调用"""
        return self.map(exc)


# 创建 Paramiko 异常映射器实例
_paramiko_mapper: Optional[ExceptionMapper] = None


def get_paramiko_exception_mapper() -> ExceptionMapper:
    """
    获取 Paramiko 异常映射器（单例）
    
    Returns:
        ExceptionMapper: 配置好的异常映射器
    """
    global _paramiko_mapper
    
    if _paramiko_mapper is None:
        _paramiko_mapper = ExceptionMapper()
        
        # 延迟导入，避免循环依赖
        try:
            import paramiko
            from rprobe.backends.base import (
                AuthenticationError,
                ConnectionError,
                SSHException,
                ChannelException,
            )
            
            # 注册类型映射
            _paramiko_mapper.register(
                paramiko.AuthenticationException,
                lambda e: AuthenticationError(f"认证失败: {e}")
            )
            
            _paramiko_mapper.register(
                paramiko.SSHException,
                lambda e: SSHException(f"SSH错误: {e}")
            )
            
            # 注册消息映射（细粒度控制）
            _paramiko_mapper.register_by_message(
                "no existing session",
                lambda e: ConnectionError(f"SSH连接失败（无有效会话）: {e}")
            )
            
            _paramiko_mapper.register_by_message(
                "connection refused",
                lambda e: ConnectionError(f"连接被拒绝: {e}")
            )
            
            _paramiko_mapper.register_by_message(
                "timeout",
                lambda e: ConnectionError(f"连接超时: {e}")
            )
            
            _paramiko_mapper.register_by_message(
                "name or service not known",
                lambda e: ConnectionError(f"无法解析主机名: {e}")
            )
            
            logger.debug("Paramiko 异常映射器初始化完成")
            
        except ImportError:
            logger.warning("paramiko 未安装，异常映射器将不可用")
    
    return _paramiko_mapper


def map_paramiko_exception(exc: Exception) -> Exception:
    """
    便捷函数：映射 Paramiko 异常
    
    Args:
        exc: Paramiko 异常
        
    Returns:
        映射后的项目自定义异常
    """
    mapper = get_paramiko_exception_mapper()
    return mapper.map(exc)


# 装饰器：自动映射异常
def map_exceptions(mapper: Optional[ExceptionMapper] = None):
    """
    异常映射装饰器
    
    自动捕获方法中的异常并映射到目标异常类型。
    
    Example:
        @map_exceptions()
        def connect(self, ...):
            # 可能抛出 paramiko 异常
            self._client.connect(...)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                nonlocal mapper
                if mapper is None:
                    mapper = get_paramiko_exception_mapper()
                
                mapped = mapper.map(e)
                if mapped is not e:
                    raise mapped from e
                raise
        
        return wrapper
    return decorator


if __name__ == "__main__":
    # 测试代码
    mapper = get_paramiko_exception_mapper()
    
    # 测试映射
    class MockSSHException(Exception):
        pass
    
    class MockAuthException(MockSSHException):
        pass
    
    # 注册测试映射
    mapper.register(MockAuthException, lambda e: Exception(f"认证失败: {e}"))
    mapper.register_by_message("timeout", lambda e: Exception(f"超时: {e}"))
    
    # 测试
    auth_exc = MockAuthException("密码错误")
    mapped = mapper.map(auth_exc)
    print(f"Auth异常映射: {type(mapped).__name__}: {mapped}")
    
    timeout_exc = MockSSHException("Connection timeout")
    mapped = mapper.map(timeout_exc)
    print(f"Timeout异常映射: {type(mapped).__name__}: {mapped}")
