"""
集成测试 - 需要真实 SSH 服务器

运行方式:
    export TEST_REAL_SSH=true
    export TEST_SSH_HOST=your-host
    export TEST_SSH_USER=your-user
    export TEST_SSH_PASS=your-password
    python -m pytest tests/integration/ -v --run-integration
"""

import pytest

from src import SSHClient
from src.config.models import SSHConfig


@pytest.mark.integration
class TestRealSSHConnection:
    """真实 SSH 服务器集成测试"""

    def test_exec_command_on_real_server(self, test_environment):
        """在真实服务器上测试 exec_command"""
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
            # 测试简单命令
            result = client.exec_command("echo 'Hello from SSH'")
            assert result.exit_code == 0
            assert "Hello from SSH" in result.stdout

            # 测试多行输出
            result = client.exec_command("echo 'Line1\nLine2'")
            assert "Line1" in result.stdout
            assert "Line2" in result.stdout

    def test_shell_session_on_real_server(self, test_environment):
        """在真实服务器上测试 shell_session"""
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
            # 打开 shell 会话
            prompt = client.open_shell_session()
            assert len(prompt) > 0

            # 测试环境变量保持
            client.shell_command("export TEST_VAR='Hello'")
            result = client.shell_command("echo $TEST_VAR")
            assert "Hello" in result.stdout

            # 测试目录切换
            client.shell_command("cd /tmp")
            result = client.shell_command("pwd")
            assert "/tmp" in result.stdout

            client.close_shell_session()

    def test_connection_reuse(self, test_environment):
        """测试连接复用"""
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
            # 执行多个命令，验证连接复用
            for i in range(3):
                result = client.exec_command(f"echo 'Test {i}'")
                assert result.exit_code == 0
                assert f"Test {i}" in result.stdout
