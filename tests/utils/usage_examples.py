"""
Mock 工厂使用示例和最佳实践

此文件演示如何使用 tests/utils/mock_factories 来重构测试代码，消除重复。
"""

import pytest
from unittest.mock import Mock, patch


# 旧方式: 重复代码
class TestOldStyle:
    """旧式测试风格 - 重复代码多"""

    def test_exec_command_old(self):
        """旧方式: 需要大量重复代码"""
        # 每次测试都要重复创建这些 mock
        mock_client = Mock()
        mock_transport = Mock()
        mock_channel = Mock()

        mock_transport.is_active.return_value = True
        mock_transport.open_session.return_value = mock_channel
        mock_client.get_transport.return_value = mock_transport

        mock_channel.recv_ready.return_value = False
        mock_channel.recv_stderr_ready.return_value = False
        mock_channel.exit_status_ready.return_value = True
        mock_channel.recv_exit_status.return_value = 0

        # 测试逻辑...
        assert mock_channel.exit_status_ready == True


# 新方式: 使用 Mock 工厂
class TestNewStyle:
    """新式测试风格 - 使用 Mock 工厂"""

    def test_exec_command_with_factory(self, mock_factory):
        """使用工厂创建 mock"""
        # 一行代码创建 channel
        channel = mock_factory.create_channel(exit_code=0)

        # 测试逻辑...
        assert channel.recv_exit_status() == 0

    def test_long_running_task(self, mock_factory):
        """使用长时间运行 channel"""
        channel = mock_factory.create_long_running_channel(
            data_chunks=[b"Line1\n", b"Line2\n"], exit_code=0, delay_cycles=3
        )

        # 测试逻辑...
        assert channel.recv_ready() == True

    def test_builder_pattern(self, mock_builder):
        """使用 Builder 模式"""
        channel = (
            mock_builder.with_stdout(b"Hello World")
            .with_exit_code(0)
            .with_closed(False)
            .build_channel()
        )

        # 测试逻辑...
        assert channel.recv() == b"Hello World"

    def test_full_setup(self, mock_ssh_setup):
        """使用完整 SSH 设置"""
        client, transport, channel = mock_ssh_setup(stdout=b"output", stderr=b"", exit_code=0)

        # 测试逻辑...
        assert client.get_transport() == transport
        assert transport.open_session() == channel


# ============================================================================
# 实际应用示例
# ============================================================================


class TestAsyncExecutorRefactored:
    """重构后的 async_executor 测试示例"""

    @pytest.fixture
    def mock_channel(self, mock_factory):
        """使用工厂创建长时间运行 channel"""
        return mock_factory.create_long_running_channel(
            data_chunks=[b"Line 1\n", b"Line 2\n"], exit_code=0, delay_cycles=5
        )

    @pytest.fixture
    def mock_ssh_client(self, mock_factory):
        """使用工厂创建 SSH client"""
        return mock_factory.create_ssh_client(is_connected=True)

    def test_background_task(self, mock_channel, mock_ssh_client):
        """测试后台任务 - 代码简洁清晰"""
        # 使用工厂创建的 mock，测试逻辑更聚焦
        assert mock_channel.active == True
        assert mock_ssh_client.is_connected() == True


class TestConnectionFactoryRefactored:
    """重构后的 connection_factory 测试示例"""

    def test_create_exec_channel(self, mock_factory):
        """测试 exec channel 创建"""
        transport = mock_factory.create_transport()
        channel = mock_factory.create_channel(exit_code=0)
        transport.open_session.return_value = channel

        # 测试 ConnectionFactory...
        assert transport.is_active() == True

    def test_with_pool(self, mock_factory):
        """测试连接池"""
        pool = mock_factory.create_connection_pool(pool_size=5)

        # 使用连接池...
        assert pool.size == 5


# ============================================================================
# 重构前后对比
# ============================================================================


# 重构前 (来自 test_edge_cases_advanced.py 中的重复代码)
def _setup_mock_connection_old(mock_ssh_client_class, mock_ssh_config):
    """旧版本: 到处复制的代码"""
    mock_client = Mock()
    mock_transport = Mock()
    mock_transport.is_active.return_value = True
    mock_client.get_transport.return_value = mock_transport
    mock_ssh_client_class.return_value = mock_client

    from src import SSHClient

    client = SSHClient(mock_ssh_config)
    client.connect()
    return client, mock_client, mock_transport


# 重构后 (使用工厂)
def _setup_mock_connection_new(mock_ssh_config, mock_factory):
    """新版本: 使用工厂，简洁清晰"""
    client, transport, _ = mock_factory.create_ssh_client_with_connection(config=mock_ssh_config)
    return client, client._client_mock, transport


# ============================================================================
# 最佳实践总结
# ============================================================================

"""
最佳实践:

1. **使用 SSHMockFactory 创建基础 mock**
   ```python
   channel = mock_factory.create_channel(exit_code=0)
   transport = mock_factory.create_transport()
   ```

2. **使用 create_long_running_channel 测试异步代码**
   ```python
   channel = mock_factory.create_long_running_channel(
       data_chunks=[b"data"],
       delay_cycles=3
   )
   ```

3. **使用 MockBuilder 构建复杂场景**
   ```python
   channel = (mock_builder
       .with_stdout(b"output")
       .with_exit_code(0)
       .with_closed(False)
       .build_channel())
   ```

4. **使用 create_mock_ssh_setup 快速搭建完整环境**
   ```python
   client, transport, channel = mock_ssh_setup(
       stdout=b"output",
       exit_code=0
   )
   ```

5. **在 conftest.py 中定义 fixture**
   ```python
   @pytest.fixture
   def mock_channel(mock_factory):
       return mock_factory.create_channel()
   ```

6. **避免重复代码**
   - 不要到处复制 _setup_mock_connection
   - 使用工厂方法统一创建
   - 保持测试代码简洁聚焦
"""
