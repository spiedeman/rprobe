"""
ConnectionFactory 完整测试套件
目标: 覆盖率从 45% 提升到 90%+
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from contextlib import contextmanager

from src.core.connection_factory import ConnectionFactory

# ==============================================================================
# create_exec_channel 测试
# ==============================================================================


class TestCreateExecChannel:
    """测试 create_exec_channel 方法"""

    def test_create_exec_channel_with_transport(self):
        """测试使用直接 transport 创建 exec channel"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command="ls -la", timeout=30.0
        ) as channel:
            assert channel == mock_channel
            mock_channel.settimeout.assert_called_once_with(30.0)
            mock_channel.exec_command.assert_called_once_with("ls -la")

        # 验证 channel 被关闭
        mock_channel.close.assert_called_once()

    def test_create_exec_channel_with_connection_manager(self):
        """测试使用 ConnectionManager 创建 exec channel"""
        mock_connection_manager = Mock()
        mock_transport = Mock()
        mock_channel = Mock()

        mock_connection_manager.transport = mock_transport
        mock_connection_manager.ensure_connected.return_value = None
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            connection_source=mock_connection_manager,
            use_pool=False,
            command="echo test",
            timeout=10.0,
        ) as channel:
            assert channel == mock_channel
            mock_connection_manager.ensure_connected.assert_called_once()
            mock_channel.exec_command.assert_called_once_with("echo test")

        mock_channel.close.assert_called_once()

    def test_create_exec_channel_with_pool(self):
        """测试使用 ConnectionPool 创建 exec channel"""
        mock_pool = Mock()
        mock_conn = Mock()
        mock_transport = Mock()
        mock_channel = Mock()

        # 设置连接池上下文管理器
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_conn
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_pool.get_connection.return_value = mock_context

        mock_conn.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            connection_source=mock_pool, use_pool=True, command="pwd", timeout=5.0
        ) as channel:
            assert channel == mock_channel
            mock_pool.get_connection.assert_called_once()
            mock_channel.exec_command.assert_called_once_with("pwd")

        mock_channel.close.assert_called_once()
        mock_context.__exit__.assert_called_once()

    def test_create_exec_channel_transport_priority(self):
        """测试 transport 参数优先级最高"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        mock_connection_manager = Mock()

        with ConnectionFactory.create_exec_channel(
            connection_source=mock_connection_manager,
            transport=mock_transport,
            command="whoami",
            timeout=10.0,
        ) as channel:
            assert channel == mock_channel
            # connection_source 不应该被使用
            mock_connection_manager.ensure_connected.assert_not_called()

    def test_create_exec_channel_no_source(self):
        """测试没有提供 transport 或 connection_source 时报错"""
        with pytest.raises(ValueError, match="必须提供 transport 或 connection_source"):
            with ConnectionFactory.create_exec_channel(command="test", timeout=10.0):
                pass

    def test_create_exec_channel_error_handling(self):
        """测试错误处理"""
        mock_transport = Mock()
        mock_transport.open_session.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            with ConnectionFactory.create_exec_channel(
                transport=mock_transport, command="test", timeout=10.0
            ):
                pass

    def test_create_exec_channel_cleanup_on_exception(self):
        """测试异常时正确清理"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        try:
            with ConnectionFactory.create_exec_channel(
                transport=mock_transport, command="test", timeout=10.0
            ) as channel:
                raise ValueError("Test error")
        except ValueError:
            pass

        # channel 应该被关闭
        mock_channel.close.assert_called_once()

    def test_create_exec_channel_pool_cleanup_on_exception(self):
        """测试连接池模式异常时正确清理"""
        mock_pool = Mock()
        mock_conn = Mock()
        mock_transport = Mock()
        mock_channel = Mock()

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_conn
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_pool.get_connection.return_value = mock_context

        mock_conn.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel

        try:
            with ConnectionFactory.create_exec_channel(
                connection_source=mock_pool, use_pool=True, command="test", timeout=10.0
            ) as channel:
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        mock_channel.close.assert_called_once()
        mock_context.__exit__.assert_called_once()

    def test_create_exec_channel_close_error_handling(self):
        """测试 channel 关闭时出错的情况"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_channel.close.side_effect = Exception("Close failed")
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command="test", timeout=10.0
        ) as channel:
            pass

        # 即使关闭失败也不应该抛出异常
        mock_channel.close.assert_called_once()

    def test_create_exec_channel_pool_release_error(self):
        """测试连接池释放时出错的情况"""
        mock_pool = Mock()
        mock_conn = Mock()
        mock_transport = Mock()
        mock_channel = Mock()

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_conn
        mock_context.__exit__ = MagicMock(side_effect=Exception("Release failed"))
        mock_pool.get_connection.return_value = mock_context

        mock_conn.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            connection_source=mock_pool, use_pool=True, command="test", timeout=10.0
        ) as channel:
            pass

        # 即使释放失败也不应该抛出异常
        mock_channel.close.assert_called_once()
        mock_context.__exit__.assert_called_once()

    def test_create_exec_channel_empty_command(self):
        """测试空命令"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command="", timeout=10.0
        ) as channel:
            mock_channel.exec_command.assert_called_once_with("")

    def test_create_exec_channel_long_command(self):
        """测试长命令截断日志"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        long_command = "echo " + "A" * 100

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command=long_command, timeout=10.0
        ) as channel:
            pass

        mock_channel.exec_command.assert_called_once_with(long_command)


# ==============================================================================
# create_shell_channel 测试
# ==============================================================================


class TestCreateShellChannel:
    """测试 create_shell_channel 方法"""

    def test_create_shell_channel_with_transport(self):
        """测试使用直接 transport 创建 shell channel"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_shell_channel(
            transport=mock_transport, timeout=60.0
        ) as channel:
            assert channel == mock_channel
            mock_channel.settimeout.assert_called_once_with(60.0)
            mock_channel.get_pty.assert_called_once()
            mock_channel.invoke_shell.assert_called_once()

        mock_channel.close.assert_called_once()

    def test_create_shell_channel_with_connection_manager(self):
        """测试使用 ConnectionManager 创建 shell channel"""
        mock_connection_manager = Mock()
        mock_transport = Mock()
        mock_channel = Mock()

        mock_connection_manager.transport = mock_transport
        mock_connection_manager.ensure_connected.return_value = None
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_shell_channel(
            connection_source=mock_connection_manager, use_pool=False, timeout=30.0
        ) as channel:
            assert channel == mock_channel
            mock_connection_manager.ensure_connected.assert_called_once()
            mock_channel.get_pty.assert_called_once()
            mock_channel.invoke_shell.assert_called_once()

        mock_channel.close.assert_called_once()

    def test_create_shell_channel_with_pool(self):
        """测试使用 ConnectionPool 创建 shell channel"""
        mock_pool = Mock()
        mock_conn = Mock()
        mock_transport = Mock()
        mock_channel = Mock()

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_conn
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_pool.get_connection.return_value = mock_context

        mock_conn.transport = mock_transport
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_shell_channel(
            connection_source=mock_pool, use_pool=True, timeout=30.0
        ) as channel:
            assert channel == mock_channel
            mock_pool.get_connection.assert_called_once()

        # 在 with 块外验证 __exit__ 被调用
        mock_context.__exit__.assert_called_once()

    def test_create_shell_channel_error_handling(self):
        """测试错误处理"""
        mock_transport = Mock()
        mock_transport.open_session.side_effect = Exception("Failed to open session")

        with pytest.raises(Exception, match="Failed to open session"):
            with ConnectionFactory.create_shell_channel(transport=mock_transport, timeout=10.0):
                pass

    def test_create_shell_channel_cleanup_on_exception(self):
        """测试异常时正确清理"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        try:
            with ConnectionFactory.create_shell_channel(
                transport=mock_transport, timeout=10.0
            ) as channel:
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        mock_channel.close.assert_called_once()


# ==============================================================================
# create_channel_simple 测试
# ==============================================================================


class TestCreateChannelSimple:
    """测试 create_channel_simple 方法"""

    def test_create_channel_simple_exec(self):
        """测试简单创建 exec channel"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        channel = ConnectionFactory.create_channel_simple(
            transport=mock_transport, channel_type="exec", command="ls -la", timeout=30.0
        )

        assert channel == mock_channel
        mock_channel.settimeout.assert_called_once_with(30.0)
        mock_channel.exec_command.assert_called_once_with("ls -la")
        mock_channel.get_pty.assert_not_called()

    def test_create_channel_simple_shell(self):
        """测试简单创建 shell channel"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        channel = ConnectionFactory.create_channel_simple(
            transport=mock_transport, channel_type="shell", timeout=60.0
        )

        assert channel == mock_channel
        mock_channel.settimeout.assert_called_once_with(60.0)
        mock_channel.get_pty.assert_called_once()
        mock_channel.invoke_shell.assert_called_once()
        mock_channel.exec_command.assert_not_called()

    def test_create_channel_simple_unknown_type(self):
        """测试未知 channel 类型"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with pytest.raises(ValueError, match="Unknown channel type: unknown"):
            ConnectionFactory.create_channel_simple(
                transport=mock_transport, channel_type="unknown", timeout=10.0
            )

    def test_create_channel_simple_no_command_for_shell(self):
        """测试 shell 类型不需要 command 参数"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        channel = ConnectionFactory.create_channel_simple(
            transport=mock_transport,
            channel_type="shell",
            command="",  # 空命令也应该工作
            timeout=10.0,
        )

        assert channel == mock_channel
        mock_channel.get_pty.assert_called_once()
        mock_channel.invoke_shell.assert_called_once()


# ==============================================================================
# 集成测试
# ==============================================================================


class TestConnectionFactoryIntegration:
    """集成测试 - 完整工作流程"""

    def test_exec_channel_full_lifecycle(self):
        """测试 exec channel 完整生命周期"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        # 1. 创建 channel
        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command="echo hello", timeout=30.0
        ) as channel:
            # 2. 使用 channel
            assert channel == mock_channel

        # 3. 验证清理
        mock_channel.close.assert_called_once()

    def test_shell_channel_full_lifecycle(self):
        """测试 shell channel 完整生命周期"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_shell_channel(
            transport=mock_transport, timeout=60.0
        ) as channel:
            assert channel == mock_channel
            mock_channel.get_pty.assert_called_once()
            mock_channel.invoke_shell.assert_called_once()

        mock_channel.close.assert_called_once()

    def test_simple_channel_full_lifecycle(self):
        """测试简单 channel 完整生命周期"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        # 创建（非上下文管理器）
        channel = ConnectionFactory.create_channel_simple(
            transport=mock_transport, channel_type="exec", command="ls", timeout=10.0
        )

        assert channel == mock_channel

        # 手动关闭（调用方负责）
        channel.close()
        mock_channel.close.assert_called_once()

    def test_mixed_usage_patterns(self):
        """测试混合使用模式"""
        mock_transport = Mock()

        # 第一个调用创建 exec channel
        mock_channel_exec = Mock()
        # 第二个调用创建 shell channel
        mock_channel_shell = Mock()

        mock_transport.open_session.side_effect = [mock_channel_exec, mock_channel_shell]

        # 使用上下文管理器创建 exec
        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command="echo test", timeout=10.0
        ) as channel:
            assert channel == mock_channel_exec

        # 使用简单方法创建 shell
        channel = ConnectionFactory.create_channel_simple(
            transport=mock_transport, channel_type="shell", timeout=10.0
        )
        assert channel == mock_channel_shell

        # 验证 exec channel 已被关闭
        mock_channel_exec.close.assert_called_once()
        # shell channel 还未关闭
        mock_channel_shell.close.assert_not_called()


# ==============================================================================
# 边界情况测试
# ==============================================================================


class TestEdgeCases:
    """边界情况测试"""

    def test_zero_timeout(self):
        """测试零超时"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command="test", timeout=0.0
        ) as channel:
            mock_channel.settimeout.assert_called_once_with(0.0)

    def test_negative_timeout(self):
        """测试负超时（应该也能工作）"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command="test", timeout=-1.0
        ) as channel:
            mock_channel.settimeout.assert_called_once_with(-1.0)

    def test_very_long_command(self):
        """测试超长命令"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        long_command = "echo " + "A" * 1000

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command=long_command, timeout=10.0
        ) as channel:
            mock_channel.exec_command.assert_called_once_with(long_command)

    def test_special_characters_in_command(self):
        """测试特殊字符命令"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        special_command = "echo 'hello world' | grep 'test' > /tmp/output.txt"

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command=special_command, timeout=10.0
        ) as channel:
            mock_channel.exec_command.assert_called_once_with(special_command)

    def test_unicode_command(self):
        """测试 Unicode 命令"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        unicode_command = "echo '你好世界'"

        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command=unicode_command, timeout=10.0
        ) as channel:
            mock_channel.exec_command.assert_called_once_with(unicode_command)

    def test_channel_type_case_sensitivity(self):
        """测试 channel 类型大小写"""
        mock_transport = Mock()
        mock_channel = Mock()
        mock_transport.open_session.return_value = mock_channel

        # 小写的 exec 应该工作
        with ConnectionFactory.create_exec_channel(
            transport=mock_transport, command="test", timeout=10.0
        ) as channel:
            pass

        # 未知类型应该报错
        with pytest.raises(ValueError):
            ConnectionFactory.create_channel_simple(
                transport=mock_transport, channel_type="EXEC", timeout=10.0  # 大写
            )
