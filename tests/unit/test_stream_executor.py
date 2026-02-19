"""
StreamExecutor 单元测试

测试流式命令执行器的核心功能，使用 Mock 对象模拟依赖。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from src.core.stream_executor import StreamExecutor
from src.core.models import CommandResult
from src.config.models import SSHConfig


@pytest.fixture
def mock_ssh_client():
    """创建 Mock SSHClient"""
    client = Mock()
    client._config = SSHConfig(
        host="test.example.com",
        username="test",
        password="test",
        timeout=30.0,
        command_timeout=60.0,
    )
    client._use_pool = False
    return client


@pytest.fixture
def mock_channel():
    """创建 Mock SSH Channel"""
    channel = Mock()
    channel.recv_ready.return_value = False
    channel.recv_stderr_ready.return_value = False
    channel.exit_status_ready = False
    channel.closed = True
    return channel


@pytest.fixture
def mock_transport():
    """创建 Mock SSH Transport"""
    transport = Mock()
    transport.is_active.return_value = True
    return transport


class TestStreamExecutorInit:
    """测试 StreamExecutor 初始化"""

    def test_init_with_config(self, mock_ssh_client):
        """测试使用配置初始化"""
        with patch("src.core.stream_executor.create_receiver") as mock_create:
            mock_receiver = Mock()
            mock_receiver.mode = "ADAPTIVE"
            mock_create.return_value = mock_receiver

            executor = StreamExecutor(mock_ssh_client)

            assert executor._client == mock_ssh_client
            assert executor._config == mock_ssh_client._config
            assert executor._receiver == mock_receiver
            mock_create.assert_called_once_with(mock_ssh_client._config)


class TestStreamExecutorExecute:
    """测试 StreamExecutor 执行功能"""

    def test_execute_with_pool(self, mock_ssh_client, mock_channel, mock_transport):
        """测试使用连接池执行"""
        mock_ssh_client._use_pool = True

        # 设置 Mock 连接池
        mock_conn = Mock()
        mock_conn.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel

        mock_pool = Mock()
        mock_pool.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_pool.get_connection.return_value.__exit__ = Mock(return_value=False)
        mock_ssh_client._pool = mock_pool

        # 设置 Mock 接收器
        with patch("src.core.stream_executor.create_receiver") as mock_create:
            mock_receiver = Mock()
            mock_receiver.recv_stream.return_value = 0
            mock_create.return_value = mock_receiver

            executor = StreamExecutor(mock_ssh_client)

            # 执行测试
            chunks = []

            def handler(stdout, stderr):
                if stdout:
                    chunks.append(stdout)

            result = executor.execute("echo test", handler, timeout=10.0)

            # 验证结果
            assert isinstance(result, CommandResult)
            assert result.exit_code == 0
            assert result.stdout == ""
            assert result.stderr == ""
            assert result.command == "echo test"
            assert result.execution_time >= 0

    def test_execute_direct(self, mock_ssh_client, mock_channel, mock_transport):
        """测试直接连接执行"""
        mock_ssh_client._use_pool = False

        # 设置 Mock 连接
        mock_connection = Mock()
        mock_connection.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel
        mock_ssh_client._connection = mock_connection

        # 设置 Mock 接收器
        with patch("src.core.stream_executor.create_receiver") as mock_create:
            mock_receiver = Mock()
            mock_receiver.recv_stream.return_value = 0
            mock_create.return_value = mock_receiver

            executor = StreamExecutor(mock_ssh_client)

            # 执行测试
            chunks = []

            def handler(stdout, stderr):
                if stdout:
                    chunks.append(stdout)

            result = executor.execute("echo test", handler)

            # 验证结果
            assert isinstance(result, CommandResult)
            assert result.exit_code == 0
            mock_connection.ensure_connected.assert_called_once()


class TestStreamExecutorTimeout:
    """测试 StreamExecutor 超时处理"""

    def test_execute_timeout(self, mock_ssh_client, mock_channel, mock_transport):
        """测试执行超时"""
        mock_ssh_client._use_pool = False

        mock_connection = Mock()
        mock_connection.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel
        mock_ssh_client._connection = mock_connection

        with patch("src.core.stream_executor.create_receiver") as mock_create:
            mock_receiver = Mock()
            mock_receiver.recv_stream.side_effect = TimeoutError("Command timeout")
            mock_create.return_value = mock_receiver

            executor = StreamExecutor(mock_ssh_client)

            with pytest.raises(TimeoutError):
                executor.execute("sleep 100", lambda x, y: None, timeout=1.0)


class TestStreamExecutorErrorHandling:
    """测试 StreamExecutor 错误处理"""

    def test_execute_connection_error(self, mock_ssh_client, mock_transport):
        """测试连接错误"""
        mock_ssh_client._use_pool = False

        mock_connection = Mock()
        mock_connection.transport = mock_transport
        mock_transport.open_session.side_effect = Exception("Connection failed")
        mock_ssh_client._connection = mock_connection

        with patch("src.core.stream_executor.create_receiver") as mock_create:
            mock_receiver = Mock()
            mock_create.return_value = mock_receiver

            executor = StreamExecutor(mock_ssh_client)

            with pytest.raises(RuntimeError) as exc_info:
                executor.execute("echo test", lambda x, y: None)

            assert "流式命令执行失败" in str(exc_info.value)

    def test_execute_channel_close_error(self, mock_ssh_client, mock_channel, mock_transport):
        """测试通道关闭错误处理"""
        mock_ssh_client._use_pool = False

        mock_connection = Mock()
        mock_connection.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel
        mock_ssh_client._connection = mock_connection

        # 模拟通道关闭时抛出异常
        mock_channel.close.side_effect = Exception("Close error")

        with patch("src.core.stream_executor.create_receiver") as mock_create:
            mock_receiver = Mock()
            mock_receiver.recv_stream.return_value = 0
            mock_create.return_value = mock_receiver

            executor = StreamExecutor(mock_ssh_client)

            # 不应该抛出异常，只是记录警告
            result = executor.execute("echo test", lambda x, y: None)
            assert result.exit_code == 0


class TestStreamExecutorCallback:
    """测试 StreamExecutor 回调功能"""

    def test_callback_with_multiple_chunks(self, mock_ssh_client, mock_channel, mock_transport):
        """测试多次回调数据块"""
        mock_ssh_client._use_pool = False

        mock_connection = Mock()
        mock_connection.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel
        mock_ssh_client._connection = mock_connection

        received_chunks = []

        def mock_recv_stream(channel, handler, timeout, transport):
            # 模拟多次数据接收
            handler(b"chunk1", b"")
            handler(b"chunk2", b"")
            handler(b"chunk3", b"")
            return 0

        with patch("src.core.stream_executor.create_receiver") as mock_create:
            mock_receiver = Mock()
            mock_receiver.recv_stream = mock_recv_stream
            mock_create.return_value = mock_receiver

            executor = StreamExecutor(mock_ssh_client)

            def handler(stdout, stderr):
                if stdout:
                    received_chunks.append(stdout)

            result = executor.execute("cat file", handler)

            assert len(received_chunks) == 3
            assert b"chunk1" in received_chunks
            assert b"chunk2" in received_chunks
            assert b"chunk3" in received_chunks

    def test_callback_with_stderr(self, mock_ssh_client, mock_channel, mock_transport):
        """测试 stderr 回调"""
        mock_ssh_client._use_pool = False

        mock_connection = Mock()
        mock_connection.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel
        mock_ssh_client._connection = mock_connection

        received_stdout = []
        received_stderr = []

        def mock_recv_stream(channel, handler, timeout, transport):
            handler(b"stdout_data", b"stderr_data")
            return 1  # 非零退出码

        with patch("src.core.stream_executor.create_receiver") as mock_create:
            mock_receiver = Mock()
            mock_receiver.recv_stream = mock_recv_stream
            mock_create.return_value = mock_receiver

            executor = StreamExecutor(mock_ssh_client)

            def handler(stdout, stderr):
                if stdout:
                    received_stdout.append(stdout)
                if stderr:
                    received_stderr.append(stderr)

            result = executor.execute("command", handler)

            assert len(received_stdout) == 1
            assert len(received_stderr) == 1
            assert received_stdout[0] == b"stdout_data"
            assert received_stderr[0] == b"stderr_data"
            assert result.exit_code == 1


class TestStreamExecutorConfig:
    """测试 StreamExecutor 配置处理"""

    def test_default_timeout_from_config(self, mock_ssh_client, mock_channel, mock_transport):
        """测试从配置获取默认超时"""
        mock_ssh_client._use_pool = False
        mock_ssh_client._config.command_timeout = 120.0

        mock_connection = Mock()
        mock_connection.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel
        mock_ssh_client._connection = mock_connection

        with patch("src.core.stream_executor.create_receiver") as mock_create:
            mock_receiver = Mock()
            mock_receiver.recv_stream.return_value = 0
            mock_create.return_value = mock_receiver

            executor = StreamExecutor(mock_ssh_client)

            # 不传入 timeout，应该使用配置中的 120.0
            result = executor.execute("echo test", lambda x, y: None)

            # 验证通道设置了正确的超时
            mock_channel.settimeout.assert_called_once_with(120.0)

    def test_override_timeout(self, mock_ssh_client, mock_channel, mock_transport):
        """测试覆盖配置超时"""
        mock_ssh_client._use_pool = False
        mock_ssh_client._config.command_timeout = 120.0

        mock_connection = Mock()
        mock_connection.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel
        mock_ssh_client._connection = mock_connection

        with patch("src.core.stream_executor.create_receiver") as mock_create:
            mock_receiver = Mock()
            mock_receiver.recv_stream.return_value = 0
            mock_create.return_value = mock_receiver

            executor = StreamExecutor(mock_ssh_client)

            # 传入 timeout 覆盖配置
            result = executor.execute("echo test", lambda x, y: None, timeout=30.0)

            # 验证通道使用了传入的超时
            mock_channel.settimeout.assert_called_once_with(30.0)
