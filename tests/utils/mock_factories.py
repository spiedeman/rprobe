"""
Mock 工厂模块 - 提供标准化的 Mock 对象创建

此模块用于消除测试代码中的重复，提供一致、可复用的 Mock 对象。
"""
from unittest.mock import Mock, MagicMock
from typing import Optional, List, Any


class SSHMockFactory:
    """
    SSH 相关 Mock 工厂
    
    提供创建标准化 Mock 对象的静态方法，用于测试 SSH 连接、Channel、Transport 等。
    
    Example:
        # 创建 Transport Mock
        transport = SSHMockFactory.create_transport()
        
        # 创建 Channel Mock
        channel = SSHMockFactory.create_channel(
            stdout_data=b"Hello World",
            exit_code=0
        )
        
        # 创建完整的 SSHClient Mock
        client = SSHMockFactory.create_ssh_client()
    """
    
    @staticmethod
    def create_transport(
        is_active: bool = True,
        is_authenticated: bool = True
    ) -> Mock:
        """
        创建 Transport Mock
        
        Args:
            is_active: Transport 是否处于活动状态
            is_authenticated: 是否已认证
            
        Returns:
            Mock: 配置好的 Transport Mock
        """
        transport = Mock()
        transport.is_active.return_value = is_active
        transport.is_authenticated.return_value = is_authenticated
        return transport
    
    @staticmethod
    def create_channel(
        stdout_data: bytes = b"",
        stderr_data: bytes = b"",
        exit_code: int = 0,
        closed: bool = True,
        active: bool = True,
        exit_status_ready: bool = True,
        recv_ready_sequence: Optional[List[bool]] = None,
        recv_data_sequence: Optional[List[bytes]] = None
    ) -> Mock:
        """
        创建 Channel Mock
        
        Args:
            stdout_data: 标准输出数据（用于单次 recv）
            stderr_data: 标准错误数据（用于单次 recv_stderr）
            exit_code: 退出码
            closed: 是否已关闭
            active: 是否活动（用于 async_executor 等模块）
            exit_status_ready: exit_status_ready 的值（用于 async_executor）
            recv_ready_sequence: recv_ready 的返回值序列
            recv_data_sequence: recv 的返回值序列
            
        Returns:
            Mock: 配置好的 Channel Mock
            
        Example:
            # 基本使用
            channel = SSHMockFactory.create_channel(
                stdout_data=b"Hello\n",
                exit_code=0
            )
            
            # 多数据读取
            channel = SSHMockFactory.create_channel(
                recv_ready_sequence=[True, True, False],
                recv_data_sequence=[b"Line1\n", b"Line2\n"]
            )
        """
        channel = MagicMock()
        
        # 基本状态
        channel.closed = closed
        channel.active = active
        channel.eof_received = closed
        
        # 如果提供了序列，使用 side_effect
        if recv_ready_sequence is not None:
            channel.recv_ready.side_effect = recv_ready_sequence
        else:
            channel.recv_ready.return_value = False
            
        if recv_data_sequence is not None:
            channel.recv.side_effect = recv_data_sequence
        else:
            channel.recv.return_value = stdout_data
        
        # stderr
        channel.recv_stderr_ready.return_value = False
        channel.recv_stderr.return_value = stderr_data
        
        # exit status - 对于 async_executor 等模块使用属性而非方法
        channel.exit_status_ready = exit_status_ready
        channel.recv_exit_status.return_value = exit_code
        
        return channel
    
    @staticmethod
    def create_long_running_channel(
        data_chunks: Optional[List[bytes]] = None,
        exit_code: int = 0,
        delay_cycles: int = 3
    ) -> Mock:
        """
        创建长时间运行的 Channel Mock
        
        适用于测试后台任务、长时间命令等场景。
        
        Args:
            data_chunks: 数据块列表，逐步返回
            exit_code: 最终退出码
            delay_cycles: 多少轮后才报告完成
            
        Returns:
            Mock: 配置好的长时间运行 Channel Mock
        """
        channel = MagicMock()
        channel.closed = False
        channel.active = True
        channel.eof_received = False
        
        # 数据读取
        recv_call_count = [0]
        def recv_side_effect(*args, **kwargs):
            recv_call_count[0] += 1
            if data_chunks and recv_call_count[0] <= len(data_chunks):
                return data_chunks[recv_call_count[0] - 1]
            return b""
        
        # recv_ready - 有数据时返回 True，delay_cycles 后返回 False
        ready_call_count = [0]
        def recv_ready_side_effect(*args, **kwargs):
            ready_call_count[0] += 1
            if ready_call_count[0] <= delay_cycles:
                return True
            return False
        
        channel.recv_ready.side_effect = recv_ready_side_effect
        channel.recv.side_effect = recv_side_effect
        channel.recv_stderr_ready.return_value = False
        
        # exit_status_ready - 延迟返回 True
        exit_call_count = [0]
        def exit_status_ready_side_effect(*args, **kwargs):
            exit_call_count[0] += 1
            return exit_call_count[0] > delay_cycles
        
        # 如果是函数调用方式
        if hasattr(channel, 'exit_status_ready'):
            if callable(channel.exit_status_ready):
                channel.exit_status_ready.side_effect = exit_status_ready_side_effect
            else:
                channel.exit_status_ready = False
        
        channel.recv_exit_status.return_value = exit_code
        
        return channel
    
    @staticmethod
    def create_ssh_client(
        is_connected: bool = True,
        transport_active: bool = True
    ) -> Mock:
        """
        创建 SSHClient Mock
        
        Args:
            is_connected: 是否已连接
            transport_active: Transport 是否活动
            
        Returns:
            Mock: 配置好的 SSHClient Mock
        """
        client = Mock()
        transport = SSHMockFactory.create_transport(
            is_active=transport_active,
            is_authenticated=is_connected
        )
        client.get_transport.return_value = transport
        client.is_connected.return_value = is_connected
        return client
    
    @staticmethod
    def create_connection_manager(
        is_connected: bool = True,
        transport_active: bool = True
    ) -> Mock:
        """
        创建 ConnectionManager Mock
        
        Args:
            is_connected: 是否已连接
            transport_active: Transport 是否活动
            
        Returns:
            Mock: 配置好的 ConnectionManager Mock
        """
        manager = Mock()
        transport = SSHMockFactory.create_transport(
            is_active=transport_active
        )
        manager.transport = transport
        manager.is_connected.return_value = is_connected
        manager.ensure_connected.return_value = None
        return manager
    
    @staticmethod
    def create_connection_pool(
        pool_size: int = 5,
        available_connections: int = 3
    ) -> Mock:
        """
        创建 ConnectionPool Mock
        
        Args:
            pool_size: 连接池大小
            available_connections: 可用连接数
            
        Returns:
            Mock: 配置好的 ConnectionPool Mock
        """
        pool = Mock()
        pool.size = pool_size
        pool.available = available_connections
        
        # 创建连接上下文
        def create_connection_context():
            conn = Mock()
            conn.transport = SSHMockFactory.create_transport()
            
            context = MagicMock()
            context.__enter__ = Mock(return_value=conn)
            context.__exit__ = Mock(return_value=None)
            return context
        
        pool.get_connection.return_value = create_connection_context()
        return pool
    
    @staticmethod
    def create_receiver_config(
        recv_mode: str = "auto",
        timeout: float = 30.0
    ) -> Mock:
        """
        创建 Receiver 配置 Mock
        
        Args:
            recv_mode: 接收模式 (select/adaptive/original/auto)
            timeout: 超时时间
            
        Returns:
            Mock: 配置好的配置 Mock
        """
        config = Mock()
        config.recv_mode = recv_mode
        config.timeout = timeout
        config.command_timeout = timeout
        return config


class MockBuilder:
    """
    Mock 构建器 - 链式 API 创建复杂 Mock
    
    Example:
        builder = MockBuilder()
        channel = (builder
            .with_stdout(b"Hello")
            .with_exit_code(0)
            .with_closed(False)
            .build_channel())
    """
    
    def __init__(self):
        self._stdout_data = b""
        self._stderr_data = b""
        self._exit_code = 0
        self._closed = True
        self._active = True
        self._recv_ready_sequence = None
        self._recv_data_sequence = None
    
    def with_stdout(self, data: bytes) -> 'MockBuilder':
        """设置标准输出"""
        self._stdout_data = data
        return self
    
    def with_stderr(self, data: bytes) -> 'MockBuilder':
        """设置标准错误"""
        self._stderr_data = data
        return self
    
    def with_exit_code(self, code: int) -> 'MockBuilder':
        """设置退出码"""
        self._exit_code = code
        return self
    
    def with_closed(self, closed: bool) -> 'MockBuilder':
        """设置关闭状态"""
        self._closed = closed
        return self
    
    def with_active(self, active: bool) -> 'MockBuilder':
        """设置活动状态"""
        self._active = active
        return self
    
    def with_recv_sequence(self, ready_seq: List[bool], data_seq: List[bytes]) -> 'MockBuilder':
        """设置接收序列"""
        self._recv_ready_sequence = ready_seq
        self._recv_data_sequence = data_seq
        return self
    
    def build_channel(self) -> Mock:
        """构建 Channel Mock"""
        return SSHMockFactory.create_channel(
            stdout_data=self._stdout_data,
            stderr_data=self._stderr_data,
            exit_code=self._exit_code,
            closed=self._closed,
            active=self._active,
            recv_ready_sequence=self._recv_ready_sequence,
            recv_data_sequence=self._recv_data_sequence
        )


# 便捷函数
def create_mock_ssh_setup(
    stdout: bytes = b"",
    stderr: bytes = b"",
    exit_code: int = 0
) -> tuple:
    """
    创建完整的 Mock SSH 设置
    
    Args:
        stdout: 标准输出
        stderr: 标准错误
        exit_code: 退出码
        
    Returns:
        tuple: (client, transport, channel) mocks
    """
    transport = SSHMockFactory.create_transport()
    channel = SSHMockFactory.create_channel(
        stdout_data=stdout,
        stderr_data=stderr,
        exit_code=exit_code
    )
    transport.open_session.return_value = channel
    
    client = SSHMockFactory.create_ssh_client()
    client.get_transport.return_value = transport
    
    return client, transport, channel
