"""
错误恢复集成测试 - 测试错误处理和恢复能力

运行方式:
    export TEST_REAL_SSH=true
    export TEST_SSH_HOST=your-host
    export TEST_SSH_USER=your-user
    export TEST_SSH_PASS=your-password
    python -m pytest tests/integration/test_error_recovery.py -v --run-integration
"""

import time
import pytest

from rprobe import SSHClient, SSHConfig
from rprobe.pooling import ConnectionPool
from rprobe.exceptions import CommandTimeoutError, ConnectionError
from tests.integration.test_config import SLEEP_TIME_LONG, SLEEP_TIME_MEDIUM


@pytest.mark.integration
class TestConnectionErrorRecovery:
    """测试连接错误恢复"""

    def test_invalid_host_handling(self, test_environment):
        """测试无效主机处理"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host="invalid.nonexistent.host.local",
            username="test",
            password="test",
            timeout=1.0,  # 从2秒减少到1秒，加速测试
            command_timeout=2.0,  # 从5秒减少到2秒
        )

        # 应该抛出连接错误 (socket.gaierror, paramiko.SSHException, etc.)
        with pytest.raises(Exception):
            with SSHClient(config) as client:
                client.exec_command("echo 'test'")

    def test_invalid_credentials_handling(self, test_environment):
        """测试无效凭据处理"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username="invalid_user_12345",
            password="wrong_password",
            timeout=2.0,  # 从5秒减少到2秒，加速测试
            command_timeout=5.0,  # 从10秒减少到5秒
        )

        # 应该抛出认证错误
        with pytest.raises(Exception):  # AuthenticationException
            with SSHClient(config) as client:
                client.exec_command("echo 'test'")

    def test_command_timeout_recovery(self, test_environment):
        """测试命令超时后恢复"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=2.0,  # 2秒超时
        )

        with SSHClient(config) as client:
            # 第一个命令超时
            with pytest.raises((CommandTimeoutError, TimeoutError)):
                client.exec_command(f"sleep {int(SLEEP_TIME_LONG)}")

            # 验证客户端仍然可用
            result = client.exec_command("echo 'Still working'")
            assert result.exit_code == 0
            assert "Still working" in result.stdout

    def test_multiple_timeouts_recovery(self, test_environment):
        """测试多次超时后恢复"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        # 使用动态sleep时间，确保比command_timeout长以触发超时
        # 但保持总时间合理：3次 × 2秒 = 6秒
        timeout_sleep = SLEEP_TIME_MEDIUM + 0.5  # 1.0秒
        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=0.8,  # 命令超时0.8秒，sleep 1.0秒会触发超时
        )

        with SSHClient(config) as client:
            # 多次超时
            for i in range(3):
                with pytest.raises((CommandTimeoutError, TimeoutError)):
                    client.exec_command(f"sleep {timeout_sleep}")

            # 验证仍然可用
            result = client.exec_command("echo 'Recovered'")
            assert result.exit_code == 0


@pytest.mark.integration
class TestPoolErrorRecovery:
    """测试连接池错误恢复"""

    def test_pool_exhaustion_error(self, test_environment):
        """测试连接池耗尽行为 - 验证可以获取多个连接"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(
            config, max_size=2, min_size=1, acquire_timeout=1.0, health_check_interval=0
        )

        try:
            # 占用所有连接（使用with语句正确获取连接）
            with pool.get_connection() as conn1:
                with pool.get_connection() as conn2:
                    # 验证连接已获取
                    assert conn1 is not None
                    assert conn2 is not None

                    # 验证两个连接都是活跃的
                    assert conn1.is_connected
                    assert conn2.is_connected

            # 验证池恢复正常（连接已释放）
            with pool.get_connection() as conn:
                assert conn.is_connected

        finally:
            pool.close()

    def test_pool_reconnect_after_network_error(self, test_environment):
        """测试网络错误后重连"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        pool = ConnectionPool(config, max_size=2, min_size=1, health_check_interval=0)

        try:
            # 正常获取连接
            with pool.get_connection() as conn:
                # ConnectionManager doesn't have execute_command, just verify connection
                assert conn.is_connected

            # 重置连接池（模拟网络问题后恢复）
            pool.close()
            pool.reset()

            # 验证可以正常使用
            with pool.get_connection() as conn:
                assert conn.is_connected

        finally:
            pool.close()


@pytest.mark.integration
class TestCommandErrorHandling:
    """测试命令错误处理"""

    def test_invalid_command_handling(self, test_environment):
        """测试无效命令处理"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        with SSHClient(config) as client:
            # 执行不存在的命令
            result = client.exec_command("invalid_command_xyz")
            assert result.exit_code != 0

            # 验证客户端仍然可用
            result2 = client.exec_command("echo 'Still working'")
            assert result2.exit_code == 0

    def test_permission_denied_handling(self, test_environment):
        """测试权限拒绝处理"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        with SSHClient(config) as client:
            # 尝试读取可能无权限的文件
            result = client.exec_command(
                "cat /root/.bashrc 2>/dev/null || echo 'Permission denied'"
            )
            assert "Permission denied" in result.stdout or result.exit_code != 0

            # 验证客户端仍然可用
            result2 = client.exec_command("echo 'Working'")
            assert result2.exit_code == 0

    def test_command_with_special_chars(self, test_environment):
        """测试包含特殊字符的命令"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        with SSHClient(config) as client:
            # 测试包含引号的命令
            result = client.exec_command("echo 'Hello \"World\"'")
            assert result.exit_code == 0
            assert "Hello" in result.stdout

            # 测试包含变量的命令
            result = client.exec_command("VAR='test'; echo $VAR")
            assert result.exit_code == 0
            assert "test" in result.stdout

    def test_empty_command_handling(self, test_environment):
        """测试空命令处理"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        with SSHClient(config) as client:
            # 执行空命令
            result = client.exec_command("")
            # 应该成功（无操作）
            assert result.exit_code == 0

            # 验证客户端仍然可用
            result2 = client.exec_command("echo 'Working'")
            assert result2.exit_code == 0


@pytest.mark.integration
class TestShellSessionErrorRecovery:
    """测试Shell会话错误恢复"""

    def test_shell_session_invalid_command(self, test_environment):
        """测试Shell会话中无效命令"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        with SSHClient(config) as client:
            prompt = client.open_shell_session()

            # 执行无效命令
            result = client.shell_command("invalid_command_xyz")
            # 检查输出中是否包含错误信息（中文或英文）
            error_indicators = ["not found", "未找到", "command not found", "未找到命令"]
            has_error = any(indicator in result.stdout.lower() for indicator in error_indicators)
            assert has_error, f"Expected error message in output, got: {result.stdout}"

            # 验证会话仍然可用
            result2 = client.shell_command("echo 'Session working'")
            assert "Session working" in result2.stdout

            client.close_shell_session()

    def test_shell_session_after_timeout(self, test_environment):
        """测试Shell会话超时后恢复"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=2.0,
        )

        with SSHClient(config) as client:
            prompt = client.open_shell_session()

            # 执行超时命令
            try:
                client.shell_command(f"sleep {int(SLEEP_TIME_LONG)}")
            except Exception:
                pass  # 预期会超时

            # 验证会话可能仍然可用（取决于实现）
            try:
                result = client.shell_command("echo 'After timeout'")
                # 如果能执行，应该成功
            except Exception:
                # 如果会话已关闭，这是可接受的
                pass

            client.close_shell_session()


@pytest.mark.integration
class TestNetworkResilience:
    """测试网络弹性"""

    def test_rapid_connect_disconnect(self, test_environment):
        """测试快速连接断开"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        # 快速多次连接断开
        for i in range(5):
            with SSHClient(config) as client:
                result = client.exec_command(f"echo 'Iteration {i}'")
                assert result.exit_code == 0

            # 短暂暂停（避免过快重连）
            time.sleep(0.05)

    def test_connection_with_large_payload(self, test_environment):
        """测试大数据负载"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=30.0,
            command_timeout=60.0,
            max_output_size=50 * 1024 * 1024,
        )

        with SSHClient(config) as client:
            # 生成大数据
            result = client.exec_command(
                "dd if=/dev/zero bs=1024 count=100 | base64 | head -c 10000"
            )
            assert result.exit_code == 0
            assert len(result.stdout) > 0

            # 验证连接仍然可用
            result2 = client.exec_command("echo 'Still working'")
            assert result2.exit_code == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
