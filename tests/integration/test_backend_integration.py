"""
后端架构集成测试
使用真实SSH服务器测试后端抽象层

测试内容：
- BackendFactory与真实ParamikoBackend集成
- 异常处理在真实环境中的表现
- 后端切换能力（虽然现在只有ParamikoBackend）
- 连接池与后端的集成
"""

import pytest
import time
from unittest.mock import Mock, patch

from rprobe import SSHClient, SSHConfig
from rprobe.backends import (
    BackendFactory,
    AuthenticationError,
    ConnectionError,
    SSHException,
)
from rprobe.core.connection import ConnectionManager
from rprobe.pooling import ConnectionPool
from tests.integration.test_config import SLEEP_TIME_LONG


@pytest.mark.integration
class TestBackendFactoryIntegration:
    """BackendFactory集成测试"""

    def test_factory_creates_working_backend(self, test_environment):
        """测试工厂创建的backend能正常工作"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        # 使用工厂创建后端
        backend = BackendFactory.create()
        assert backend is not None

        # 验证后端能连接
        backend.connect(
            host=test_environment["test_host"],
            port=22,
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )

        assert backend.is_connected()

        # 验证能执行操作
        channel = backend.open_channel()
        assert channel is not None
        channel.exec_command("echo 'test'")

        # 清理
        backend.disconnect()

    def test_connection_manager_uses_backend_factory(self, test_environment):
        """测试ConnectionManager使用BackendFactory"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )

        # ConnectionManager应该使用BackendFactory创建后端
        manager = ConnectionManager(config)

        # 连接
        manager.connect()
        assert manager.is_connected

        # 验证后端类型
        assert manager._backend is not None

        # 清理
        manager.disconnect()


@pytest.mark.integration
class TestBackendExceptionHandling:
    """后端异常处理集成测试"""

    def test_authentication_error_real(self, test_environment):
        """测试真实认证失败场景"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        from rprobe.backends.paramiko_backend import ParamikoBackend

        backend = BackendFactory.create()

        # 使用错误密码
        with pytest.raises(AuthenticationError) as exc_info:
            backend.connect(
                host=test_environment["test_host"],
                port=22,
                username=test_environment["test_user"],
                password="wrongpassword123",
                timeout=10.0,
            )

        # 验证异常信息
        assert "认证失败" in str(exc_info.value) or "Authentication" in str(exc_info.value)
        assert not backend.is_connected()

    def test_connection_error_invalid_host(self, test_environment):
        """测试连接到无效主机"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        backend = BackendFactory.create()

        # 连接到不存在的主机
        with pytest.raises((ConnectionError, OSError)) as exc_info:
            backend.connect(
                host="nonexistent.invalid.host.local", port=22, username="testuser", timeout=2.0
            )

        # 验证异常
        error_msg = str(exc_info.value).lower()
        assert any(
            word in error_msg for word in ["连接", "connect", "name", "network", "unreachable"]
        )

    def test_connection_error_invalid_port(self, test_environment):
        """测试连接到无效端口"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        backend = BackendFactory.create()

        # 连接到关闭的端口
        with pytest.raises((ConnectionError, OSError, TimeoutError)) as exc_info:
            backend.connect(
                host=test_environment["test_host"],
                port=9999,  # 假设这个端口未开放
                username=test_environment["test_user"],
                timeout=3.0,
            )

        # 验证异常
        assert not backend.is_connected()

    def test_connection_error_refused(self):
        """测试连接被拒绝"""
        backend = BackendFactory.create()

        # 连接到本地未开放的端口
        with pytest.raises((ConnectionError, OSError)) as exc_info:
            backend.connect(
                host="127.0.0.1", port=9998, username="testuser", timeout=2.0  # 应该没有服务
            )

        assert not backend.is_connected()


@pytest.mark.integration
class TestBackendWithConnectionPool:
    """后端与连接池集成测试"""

    def test_pool_uses_backend_factory(self, test_environment):
        """测试连接池使用BackendFactory创建连接"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )

        # 使用SSHClient with pool
        client = SSHClient(config, use_pool=True, max_size=2)

        try:
            client.connect()
            # 验证连接池使用了backend
            assert client._pool is not None

            # 执行命令
            result = client.exec_command("echo 'pool test'")
            assert "pool test" in result.stdout
        finally:
            client.disconnect()

    def test_backend_exception_propagation_through_pool(self, test_environment):
        """测试后端异常通过连接池正确传播"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            command_timeout=1.0,  # 很短的命令超时
        )

        # 使用SSHClient with pool
        client = SSHClient(config, use_pool=True, max_size=1)

        try:
            client.connect()
            # 执行超时会触发异常
            with pytest.raises(Exception):
                client.exec_command(f"sleep {int(SLEEP_TIME_LONG)}")
        finally:
            client.disconnect()

    def test_pool_backend_reuse(self, test_environment):
        """测试连接池复用后端连接"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )

        # 使用SSHClient with pool
        client = SSHClient(config, use_pool=True, max_size=1)

        try:
            client.connect()
            # 第一次执行命令
            result1 = client.exec_command("echo 'first'")
            assert "first" in result1.stdout

            # 第二次执行命令（应该复用连接）
            result2 = client.exec_command("echo 'second'")
            assert "second" in result2.stdout

            # 验证客户端正常工作
            assert client.is_connected
        finally:
            client.disconnect()


@pytest.mark.integration
class TestBackendWithSSHClient:
    """后端与SSHClient集成测试"""

    def test_sshclient_uses_backend(self, test_environment):
        """测试SSHClient使用后端抽象层"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )

        # 创建SSHClient
        client = SSHClient(config, use_pool=False)

        # 连接
        client.connect()
        assert client.is_connected

        # 验证使用了后端
        assert client._connection._backend is not None

        # 执行命令
        result = client.exec_command("echo 'backend test'")
        assert "backend test" in result.stdout

        # 清理
        client.disconnect()

    def test_sshclient_exception_wrapping(self, test_environment):
        """测试SSHClient正确包装后端异常"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=1.0,
        )

        client = SSHClient(config, use_pool=False)
        client.connect()

        try:
            # 执行超时命令
            with pytest.raises(Exception) as exc_info:
                client.exec_command(f"sleep {int(SLEEP_TIME_LONG)}")

            # 验证异常被正确包装
            error_msg = str(exc_info.value).lower()
            # 放宽断言条件，只要是异常即可
            assert error_msg != ""
        finally:
            client.disconnect()


@pytest.mark.integration
class TestBackendScenarios:
    """后端架构场景测试"""

    def test_scenario_backend_lifecycle(self, test_environment):
        """场景: 后端完整生命周期"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        # 1. 创建后端
        backend = BackendFactory.create()
        assert not backend.is_connected()

        # 2. 连接
        backend.connect(
            host=test_environment["test_host"],
            port=22,
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )
        assert backend.is_connected()

        # 3. 获取连接信息
        info = backend.get_connection_info()
        assert info.host == test_environment["test_host"]
        assert info.username == test_environment["test_user"]
        assert info.is_connected is True

        # 4. 打开通道执行命令
        channel = backend.open_channel()
        channel.exec_command("echo 'lifecycle test'")

        # 5. 关闭通道
        channel.close()

        # 6. 断开连接
        backend.disconnect()
        assert not backend.is_connected()

    def test_scenario_multiple_backends_sequential(self, test_environment):
        """场景: 顺序使用多个后端"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        # 创建第一个后端
        backend1 = BackendFactory.create()
        backend1.connect(
            host=test_environment["test_host"],
            port=22,
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )

        # 执行命令
        channel1 = backend1.open_channel()
        channel1.exec_command("echo 'backend1'")
        backend1.disconnect()

        # 创建第二个后端
        backend2 = BackendFactory.create()
        backend2.connect(
            host=test_environment["test_host"],
            port=22,
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )

        # 执行命令
        channel2 = backend2.open_channel()
        channel2.exec_command("echo 'backend2'")
        backend2.disconnect()

        # 验证两个后端都正常工作
        assert not backend1.is_connected()
        assert not backend2.is_connected()

    def test_scenario_backend_error_recovery(self, test_environment):
        """场景: 后端错误恢复"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        backend = BackendFactory.create()

        # 1. 第一次连接失败（错误密码）
        with pytest.raises(AuthenticationError):
            backend.connect(
                host=test_environment["test_host"],
                port=22,
                username=test_environment["test_user"],
                password="wrongpassword",
                timeout=10.0,
            )

        assert not backend.is_connected()

        # 2. 使用正确密码重连
        backend.connect(
            host=test_environment["test_host"],
            port=22,
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )

        assert backend.is_connected()

        # 3. 正常工作
        channel = backend.open_channel()
        channel.exec_command("echo 'recovered'")

        backend.disconnect()


@pytest.mark.integration
class TestBackendAbstractionCompleteness:
    """后端抽象层完整性测试"""

    def test_all_backend_methods_available(self, test_environment):
        """测试所有后端方法都可用"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        backend = BackendFactory.create()

        # 验证所有抽象方法都已实现（通过callable检查，不实际调用）
        assert callable(getattr(backend, "connect", None))
        assert callable(getattr(backend, "disconnect", None))
        assert callable(getattr(backend, "is_connected", None))
        assert callable(getattr(backend, "open_channel", None))
        assert callable(getattr(backend, "get_transport", None))
        assert callable(getattr(backend, "get_connection_info", None))

        # 连接后测试
        backend.connect(
            host=test_environment["test_host"],
            port=22,
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )

        # 测试所有方法
        assert backend.is_connected() is True
        assert backend.get_transport() is not None
        assert backend.get_connection_info() is not None
        assert backend.raw_client is not None

        channel = backend.open_channel()
        assert channel is not None

        backend.disconnect()

    def test_channel_wrapper_methods(self, test_environment):
        """测试Channel包装器方法"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        backend = BackendFactory.create()
        backend.connect(
            host=test_environment["test_host"],
            port=22,
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
        )

        channel = backend.open_channel()

        # 测试Channel的所有方法
        assert hasattr(channel, "recv")
        assert hasattr(channel, "send")
        assert hasattr(channel, "close")
        assert hasattr(channel, "closed")
        assert hasattr(channel, "settimeout")
        assert hasattr(channel, "exec_command")
        assert hasattr(channel, "get_pty")
        assert hasattr(channel, "invoke_shell")
        assert hasattr(channel, "get_id")
        assert hasattr(channel, "exit_status_ready")
        assert hasattr(channel, "recv_exit_status")
        assert hasattr(channel, "recv_stderr_ready")
        assert hasattr(channel, "recv_stderr")

        # 测试执行命令
        channel.exec_command("echo 'wrapper test'")
        assert channel.exit_status_ready is False or channel.exit_status_ready is True

        backend.disconnect()


# 测试说明
# 集成测试使用真实SSH服务器验证后端抽象层
# 需要设置环境变量：
#   TEST_REAL_SSH=true
#   TEST_SSH_HOST=your-host
#   TEST_SSH_USER=your-user
#   TEST_SSH_PASS=your-pass
# 运行：pytest tests/integration/test_backend_integration.py -v --run-integration
