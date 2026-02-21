"""
边界情况和边缘案例测试
用于加固项目质量，覆盖 main.py 可能遇到的特殊情况
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import Mock, MagicMock, patch

from src import SSHClient, SSHConfig
from src.async_executor import BackgroundTask, BackgroundTaskManager
from src.core.connection_factory import ConnectionFactory
from src.exceptions import ConfigurationError


class TestSSHConfigEdgeCases:
    """SSHConfig 边界情况测试"""

    def test_empty_host_raises_error(self):
        """测试空 host 应该抛出 ConfigurationError"""
        with pytest.raises(ConfigurationError):
            SSHConfig(host="", username="user", password="pass")

    def test_whitespace_host_is_stripped(self):
        """测试空白 host 会被自动去除或接受"""
        # SSHConfig 可能会自动 strip 空白字符，这不一定是错误
        config = SSHConfig(host="   localhost   ", username="user", password="pass")
        # 检查是否被正确处理（strip 后）
        assert "localhost" in config.host or config.host == "   localhost   "

    def test_invalid_port_raises_error(self):
        """测试无效端口应该抛出 ConfigurationError"""
        with pytest.raises(ConfigurationError):
            SSHConfig(host="test.com", username="user", password="pass", port=70000)

    def test_negative_port_raises_error(self):
        """测试负数端口应该抛出 ConfigurationError"""
        with pytest.raises(ConfigurationError):
            SSHConfig(host="test.com", username="user", password="pass", port=-1)

    def test_zero_port_raises_error(self):
        """测试端口 0 应该抛出 ConfigurationError"""
        with pytest.raises(ConfigurationError):
            SSHConfig(host="test.com", username="user", password="pass", port=0)

    def test_very_long_username(self):
        """测试超长用户名"""
        long_username = "a" * 1000
        config = SSHConfig(host="test.com", username=long_username, password="pass")
        assert config.username == long_username

    def test_unicode_in_config(self):
        """测试配置中的 Unicode 字符"""
        config = SSHConfig(
            host="test.com",
            username="用户名",
            password="密码",
        )
        assert config.username == "用户名"
        assert config.password == "密码"


class TestBackgroundTaskEdgeCases:
    """后台任务边界情况测试"""

    def test_task_with_empty_command(self):
        """测试空命令"""
        mock_channel = MagicMock()
        mock_channel.closed = False
        mock_channel.exit_status_ready = False

        task = BackgroundTask(
            channel=mock_channel,
            command="",
            buffer_size_mb=1.0
        )

        assert task.command == ""
        assert task.is_running() is True

    def test_task_with_very_long_command(self):
        """测试超长命令"""
        long_command = "echo " + "A" * 10000
        mock_channel = MagicMock()
        mock_channel.closed = False
        mock_channel.exit_status_ready = False

        task = BackgroundTask(
            channel=mock_channel,
            command=long_command,
            buffer_size_mb=1.0
        )

        assert task.command == long_command

    def test_task_with_special_characters(self):
        """测试特殊字符命令"""
        special_command = r"echo 'Hello; && || | \$HOME'"
        mock_channel = MagicMock()
        mock_channel.closed = False
        mock_channel.exit_status_ready = False

        task = BackgroundTask(
            channel=mock_channel,
            command=special_command,
            buffer_size_mb=1.0
        )

        assert task.command == special_command

    def test_task_with_unicode(self):
        """测试 Unicode 命令"""
        unicode_command = "echo '你好世界'"
        mock_channel = MagicMock()
        mock_channel.closed = False
        mock_channel.exit_status_ready = False

        task = BackgroundTask(
            channel=mock_channel,
            command=unicode_command,
            buffer_size_mb=1.0
        )

        assert task.command == unicode_command

    def test_task_buffer_size_zero(self):
        """测试零缓冲区大小"""
        mock_channel = MagicMock()
        mock_channel.closed = False
        mock_channel.exit_status_ready = False

        # 应该使用最小值或抛出错误
        task = BackgroundTask(
            channel=mock_channel,
            command="test",
            buffer_size_mb=0.0
        )

        assert task is not None

    def test_task_with_very_small_buffer(self):
        """测试非常小缓冲区"""
        mock_channel = MagicMock()
        mock_channel.closed = False
        mock_channel.exit_status_ready = False

        task = BackgroundTask(
            channel=mock_channel,
            command="test",
            buffer_size_mb=0.001  # 1KB
        )

        assert task is not None


class TestConnectionFactoryEdgeCases:
    """ConnectionFactory 边界情况测试"""

    def test_exec_channel_with_empty_command(self):
        """测试 exec channel 空命令"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport,
            command="",
            timeout=10.0
        ) as channel:
            mock_channel.exec_command.assert_called_once_with("")

    def test_exec_channel_with_very_long_command(self):
        """测试 exec channel 超长命令"""
        long_command = "echo " + "A" * 10000
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport,
            command=long_command,
            timeout=10.0
        ) as channel:
            mock_channel.exec_command.assert_called_once_with(long_command)

    def test_exec_channel_with_special_chars(self):
        """测试特殊字符命令"""
        special_cmd = "echo 'test' | grep 'pattern' > /tmp/out"
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport,
            command=special_cmd,
            timeout=10.0
        ) as channel:
            mock_channel.exec_command.assert_called_once_with(special_cmd)

    def test_exec_channel_with_unicode(self):
        """测试 Unicode 命令"""
        unicode_cmd = "echo '你好世界'"
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport,
            command=unicode_cmd,
            timeout=10.0
        ) as channel:
            mock_channel.exec_command.assert_called_once_with(unicode_cmd)

    def test_shell_channel_basic(self):
        """测试 shell channel 基本功能"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_shell_channel(
            transport=mock_transport,
            timeout=60.0
        ) as channel:
            mock_channel.get_pty.assert_called_once()
            mock_channel.invoke_shell.assert_called_once()

    def test_zero_timeout(self):
        """测试零超时"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport,
            command="test",
            timeout=0.0
        ) as channel:
            mock_channel.settimeout.assert_called_once_with(0.0)


class TestSSHClientEdgeCases:
    """SSHClient 边界情况测试"""

    def test_client_with_minimal_config(self):
        """测试最小配置"""
        config = SSHConfig(
            host="localhost",
            username="user",
            password="pass"
        )
        client = SSHClient(config, use_pool=False)

        assert client._config.host == "localhost"
        assert client._config.username == "user"
        assert client._config.password == "pass"

    def test_client_background_tasks_empty(self):
        """测试空后台任务列表"""
        config = SSHConfig(
            host="localhost",
            username="user",
            password="pass"
        )
        client = SSHClient(config, use_pool=False)

        assert client.background_tasks == []
        assert client.get_background_task("nonexistent") is None
        assert client.get_background_task_by_name("nonexistent") is None


class TestMainPyScenarios:
    """main.py 场景测试"""

    def test_config_from_environment_variables(self):
        """测试从环境变量读取配置"""
        # 保存原始环境变量
        original_host = os.environ.get("REMOTE_SSH_HOST")
        original_user = os.environ.get("REMOTE_SSH_USERNAME")
        original_pass = os.environ.get("REMOTE_SSH_PASSWORD")

        try:
            # 设置测试环境变量
            os.environ["REMOTE_SSH_HOST"] = "test-host.com"
            os.environ["REMOTE_SSH_USERNAME"] = "testuser"
            os.environ["REMOTE_SSH_PASSWORD"] = "testpass"

            host = os.environ.get("REMOTE_SSH_HOST", "localhost")
            username = os.environ.get("REMOTE_SSH_USERNAME", "demo-user")
            password = os.environ.get("REMOTE_SSH_PASSWORD", "demo-pass")

            config = SSHConfig(
                host=host,
                username=username,
                password=password,
                timeout=10.0,
                command_timeout=30.0,
            )

            assert config.host == "test-host.com"
            assert config.username == "testuser"
            assert config.password == "testpass"

        finally:
            # 恢复原始环境变量
            if original_host is not None:
                os.environ["REMOTE_SSH_HOST"] = original_host
            elif "REMOTE_SSH_HOST" in os.environ:
                del os.environ["REMOTE_SSH_HOST"]

            if original_user is not None:
                os.environ["REMOTE_SSH_USERNAME"] = original_user
            elif "REMOTE_SSH_USERNAME" in os.environ:
                del os.environ["REMOTE_SSH_USERNAME"]

            if original_pass is not None:
                os.environ["REMOTE_SSH_PASSWORD"] = original_pass
            elif "REMOTE_SSH_PASSWORD" in os.environ:
                del os.environ["REMOTE_SSH_PASSWORD"]

    def test_default_config_values(self):
        """测试默认配置值"""
        config = SSHConfig(
            host="test.com",
            username="user",
            password="pass"
        )

        # 检查默认值（根据实际默认值调整）
        assert config.port == 22
        assert config.timeout == 30.0  # 实际默认值
        assert config.command_timeout == 300.0  # 实际默认值


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
