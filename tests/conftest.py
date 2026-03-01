"""
Pytest 配置和共享夹具
"""

import os
from unittest.mock import Mock, MagicMock

import pytest

from rprobe.config.models import SSHConfig


def pytest_addoption(parser):
    """添加自定义命令行选项"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="运行集成测试（需要真实 SSH 服务器）",
    )


def pytest_configure(config):
    """配置 pytest"""
    config.addinivalue_line("markers", "integration: 标记为集成测试（需要真实 SSH 服务器）")
    # 设置测试环境变量，用于跳过某些验证
    os.environ["TESTING"] = "true"


def pytest_collection_modifyitems(config, items):
    """修改测试收集"""
    if not config.getoption("--run-integration"):
        # 跳过集成测试目录中的测试
        skip_integration = pytest.mark.skip(reason="需要 --run-integration 选项来运行集成测试")
        for item in items:
            if "integration" in item.nodeid:
                item.add_marker(skip_integration)


@pytest.fixture
def mock_ssh_config():
    """创建测试用的 SSH 配置"""
    return SSHConfig(
        host="test.example.com",
        username="testuser",
        password="testpass123",
        port=22,
        timeout=5.0,
        command_timeout=10.0,
        max_output_size=1024 * 1024,  # 1MB
    )


@pytest.fixture
def mock_ssh_config_with_key():
    """创建使用密钥的 SSH 配置"""
    return SSHConfig(
        host="test.example.com",
        username="testuser",
        key_filename="/path/to/key",
        key_password="keypass",
        port=22,
        timeout=5.0,
    )


@pytest.fixture
def mock_paramiko_client():
    """创建 mock 的 paramiko SSHClient"""
    client = Mock()
    transport = Mock()
    transport.is_active.return_value = True
    client.get_transport.return_value = transport
    return client


@pytest.fixture
def mock_paramiko_channel():
    """创建 mock 的 paramiko Channel（向后兼容）"""
    channel = Mock()
    channel.recv_ready.return_value = False
    channel.recv_stderr_ready.return_value = False
    channel.exit_status_ready.return_value = True
    channel.recv_exit_status.return_value = 0
    channel.closed = False
    channel.eof_received = False
    return channel


@pytest.fixture
def mock_backend():
    """创建 mock SSH后端（新方式）"""
    backend = Mock()
    backend.is_connected.return_value = True
    channel = Mock()
    channel.closed = False
    channel.recv_ready.return_value = False
    channel.recv_stderr_ready.return_value = False
    channel.exit_status_ready.return_value = True
    channel.recv_exit_status.return_value = 0
    backend.open_channel.return_value = channel
    return backend


@pytest.fixture
def mock_channel():
    """创建 mock Channel（抽象层）"""
    from rprobe.backends.base import Channel

    channel = Mock(spec=Channel)
    channel.closed = False
    channel.recv_ready.return_value = False
    channel.recv_stderr_ready.return_value = False
    channel.exit_status_ready.return_value = True
    channel.recv_exit_status.return_value = 0
    return channel


@pytest.fixture
def test_environment():
    """检查测试环境变量"""
    return {
        "has_real_ssh": os.environ.get("TEST_REAL_SSH", "false").lower() == "true",
        "test_host": os.environ.get("TEST_SSH_HOST", "localhost"),
        "test_user": os.environ.get("TEST_SSH_USER", "test"),
        "test_pass": os.environ.get("TEST_SSH_PASS", ""),
    }


# ============================================================================
# Mock 工厂 Fixture
# ============================================================================


@pytest.fixture
def mock_factory():
    """提供 SSHMockFactory 类"""
    from tests.utils.mock_factories import SSHMockFactory

    return SSHMockFactory


@pytest.fixture
def mock_builder():
    """提供 MockBuilder 类"""
    from tests.utils.mock_factories import MockBuilder

    return MockBuilder()


@pytest.fixture
def mock_ssh_setup():
    """创建完整的 Mock SSH 设置 (client, transport, channel)"""
    from tests.utils.mock_factories import create_mock_ssh_setup

    return create_mock_ssh_setup
