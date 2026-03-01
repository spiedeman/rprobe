"""
后端接口契约测试

验证所有后端实现都遵循相同的接口契约。
这些测试确保新增后端或修改现有后端时不会破坏接口一致性。
"""

import pytest
import inspect
from typing import get_type_hints, Protocol, runtime_checkable
from unittest.mock import MagicMock

from rprobe.backends.base import (
    SSHBackend,
    Channel,
    Transport,
    AuthenticationError,
    ConnectionError,
    SSHException,
    ChannelException,
)


class TestBackendInterfaceContract:
    """后端接口契约测试"""

    def test_backend_has_required_methods(self):
        """验证所有后端实现都有必需的方法"""
        required_methods = [
            'connect',
            'disconnect',
            'is_connected',
            'open_channel',
            'get_transport',
            'get_connection_info',
        ]
        
        # 获取SSHBackend的所有子类
        from rprobe.backends.paramiko_backend import ParamikoBackend
        backends = [ParamikoBackend]
        
        for backend_class in backends:
            for method in required_methods:
                assert hasattr(backend_class, method), \
                    f"{backend_class.__name__} 缺少方法: {method}"

    def test_channel_has_required_methods(self):
        """验证 Channel 实现都有必需的方法"""
        required_methods = [
            'recv',
            'send',
            'close',
            'closed',
            'settimeout',
            'exec_command',
            'get_pty',
            'invoke_shell',
            'get_id',
            'exit_status_ready',
            'recv_exit_status',
            'recv_stderr_ready',
            'recv_stderr',
            'recv_ready',
            'setblocking',
            'get_transport',  # 关键方法！
            'getpeername',
            'gettimeout',
            'sendall',
            'resize_pty',
            'active',  # 后台任务监控必需！
        ]

        from rprobe.backends.paramiko_backend import ParamikoChannel

        for method in required_methods:
            assert hasattr(ParamikoChannel, method), \
                f"ParamikoChannel 缺少方法: {method}"

    def test_channel_active_property(self):
        """验证 Channel 有 active 属性且行为正确"""
        from rprobe.backends.paramiko_backend import ParamikoChannel

        # 检查 active 是属性（不是方法）
        assert isinstance(getattr(ParamikoChannel, 'active'), property), \
            "active 应该是 property"

        # 测试正常情况
        mock_channel = MagicMock()
        mock_channel.active = True
        pc = ParamikoChannel(mock_channel)
        assert pc.active is True, "active 应该返回 True"

        # 测试关闭情况
        mock_channel.active = False
        assert pc.active is False, "active 应该返回 False"

    def test_transport_has_required_methods(self):
        """验证 Transport 实现都有必需的方法"""
        required_methods = [
            'open_session',
            'is_active',
            'close',
        ]
        
        from rprobe.backends.paramiko_backend import ParamikoTransport
        
        for method in required_methods:
            assert hasattr(ParamikoTransport, method), \
                f"ParamikoTransport 缺少方法: {method}"

    def test_channel_methods_have_correct_signatures(self):
        """验证 Channel 方法的签名正确"""
        from rprobe.backends.paramiko_backend import ParamikoChannel
        
        # 检查 get_transport 返回类型
        method = getattr(ParamikoChannel, 'get_transport')
        hints = get_type_hints(method)
        return_type = hints.get('return', None)
        
        assert return_type is not None, \
            "get_transport 必须有返回类型注解"
        
        # 验证返回类型是 Optional[Transport] 或类似
        return_type_str = str(return_type)
        assert 'Transport' in return_type_str or 'Optional' in return_type_str, \
            f"get_transport 返回类型应为 Optional[Transport], 实际是 {return_type}"


class TestExceptionMappingContract:
    """异常映射契约测试"""

    def test_all_paramiko_exceptions_mapped(self):
        """验证所有Paramiko异常都有映射"""
        import paramiko
        
        from rprobe.backends.paramiko_backend import ParamikoBackend
        
        # 获取 connect 方法的异常处理
        source = inspect.getsource(ParamikoBackend.connect)
        
        # 验证关键异常类型都被捕获
        required_exceptions = [
            'AuthenticationException',
            'SSHException',
        ]
        
        for exc in required_exceptions:
            assert exc in source, \
                f"connect 方法应该捕获 {exc}"

    def test_exception_mapping_consistency(self):
        """验证异常映射的一致性"""
        # 确保相似的错误映射到相同的自定义异常
        from rprobe.backends.base import (
            AuthenticationError,
            ConnectionError,
            SSHException,
            ChannelException,
        )
        
        # 验证所有自定义异常都继承自正确的基类
        assert issubclass(AuthenticationError, Exception)
        assert issubclass(ConnectionError, Exception)
        assert issubclass(SSHException, Exception)
        assert issubclass(ChannelException, Exception)


class TestConnectionPoolContract:
    """连接池接口契约测试"""

    def test_pool_get_connection_is_contextmanager(self):
        """验证 get_connection 是上下文管理器"""
        from contextlib import AbstractContextManager
        from rprobe.pooling import ConnectionPool
        
        # 获取 get_connection 方法
        method = getattr(ConnectionPool, 'get_connection')
        
        # 检查是否有 @contextmanager 装饰器
        # 检查方法是否有 __wrapped__ 属性（被装饰器装饰）
        is_decorated = hasattr(method, '__wrapped__') or hasattr(method, '_is_contextmanager')
        
        # 或者检查返回类型（如果有的话）
        hints = get_type_hints(method)
        return_type = hints.get('return', None)
        
        if return_type is not None:
            # 验证返回类型是 Generator 或上下文管理器
            return_type_str = str(return_type)
            assert 'Generator' in return_type_str or 'ContextManager' in return_type_str, \
                f"get_connection 应该返回 Generator 或 ContextManager, 实际是 {return_type}"
        else:
            # 如果没有类型注解，检查文档字符串
            doc = method.__doc__ or ""
            assert 'context' in doc.lower() or 'yield' in doc.lower(), \
                "get_connection 应该是上下文管理器，请在文档中说明"

    def test_pool_usage_pattern(self):
        """验证连接池的正确使用模式"""
        # 这个测试确保调用方正确使用上下文管理器
        # 通过检查 _create_channel_from_pool 的代码
        from rprobe.core.connection import MultiSessionManager
        
        source = inspect.getsource(MultiSessionManager._create_channel_from_pool)
        
        # 应该使用 with 语句
        assert 'with' in source or '__enter__' in source, \
            "_create_channel_from_pool 应该使用 with 语句或 __enter__/__exit__"


@pytest.mark.contract
class TestBackendCompleteness:
    """后端完整性契约测试 - 运行时会检查"""

    def test_paramiko_backend_complete(self):
        """验证 ParamikoBackend 完整实现"""
        from rprobe.backends.paramiko_backend import ParamikoBackend, ParamikoChannel, ParamikoTransport
        
        # 验证 ParamikoBackend 实现了所有必需方法
        backend_methods = [m for m in dir(ParamikoBackend) if not m.startswith('_')]
        required_backend = ['connect', 'disconnect', 'is_connected', 'open_channel', 'get_transport']
        for method in required_backend:
            assert method in backend_methods, f"ParamikoBackend 缺少 {method}"
        
        # 验证 ParamikoChannel 实现了所有必需方法
        channel_methods = [m for m in dir(ParamikoChannel) if not m.startswith('_')]
        required_channel = ['recv', 'send', 'close', 'exec_command', 'get_transport', 'getpeername']
        for method in required_channel:
            assert method in channel_methods, f"ParamikoChannel 缺少 {method}"
        
        # 验证 ParamikoTransport 实现了所有必需方法
        transport_methods = [m for m in dir(ParamikoTransport) if not m.startswith('_')]
        required_transport = ['open_session', 'is_active', 'close']
        for method in required_transport:
            assert method in transport_methods, f"ParamikoTransport 缺少 {method}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
