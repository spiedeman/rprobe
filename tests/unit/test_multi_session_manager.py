"""
测试多会话管理器(MultiSessionManager)功能
"""

import time
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.core.connection import ConnectionManager, MultiSessionManager, SessionInfo
from src.session.shell_session import ShellSession
from src.config.models import SSHConfig


class TestMultiSessionManagerCreate:
    """测试创建会话功能"""

    def test_create_session_auto_id(self):
        """测试自动ID生成"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with (
            patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class,
            patch.object(ShellSession, "__init__", return_value=None),
            patch.object(ShellSession, "initialize", return_value="$"),
        ):

            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            mock_channel = MagicMock()
            mock_channel.get_id.return_value = 1
            mock_transport.open_session.return_value = mock_channel

            session = mgr.create_session()

            assert session is not None
            assert mgr.active_session_count == 1
            assert "session_1" in mgr.list_sessions()

    def test_create_session_custom_id(self):
        """测试自定义会话ID"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with (
            patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class,
            patch.object(ShellSession, "__init__", return_value=None),
            patch.object(ShellSession, "initialize", return_value="$"),
        ):

            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            mock_channel = MagicMock()
            mock_channel.get_id.return_value = 1
            mock_transport.open_session.return_value = mock_channel

            session = mgr.create_session("my_custom_session")

            assert "my_custom_session" in mgr.list_sessions()

    def test_create_session_duplicate_id(self):
        """测试重复会话ID报错"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with (
            patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class,
            patch.object(ShellSession, "__init__", return_value=None),
            patch.object(ShellSession, "initialize", return_value="$"),
        ):

            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            mock_channel = MagicMock()
            mock_channel.get_id.return_value = 1
            mock_transport.open_session.return_value = mock_channel

            mgr.create_session("test_session")

            # 尝试创建相同ID的会话
            with pytest.raises(ValueError) as exc_info:
                mgr.create_session("test_session")

            assert "already exists" in str(exc_info.value)

    def test_create_multiple_sessions(self):
        """测试创建多个会话"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with (
            patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class,
            patch.object(ShellSession, "__init__", return_value=None),
            patch.object(ShellSession, "initialize", return_value="$"),
        ):

            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            sessions = []
            for i in range(3):
                mock_channel = MagicMock()
                mock_channel.get_id.return_value = i + 1
                mock_transport.open_session.return_value = mock_channel

                session = mgr.create_session(f"session_{i}")
                sessions.append(session)

            assert mgr.active_session_count == 3
            assert len(mgr.list_sessions()) == 3


class TestMultiSessionManagerGet:
    """测试获取会话功能"""

    def test_get_session_existing(self):
        """测试获取存在的会话"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with (
            patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class,
            patch.object(ShellSession, "__init__", return_value=None),
            patch.object(ShellSession, "initialize", return_value="$"),
        ):

            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            mock_channel = MagicMock()
            mock_channel.get_id.return_value = 1
            mock_transport.open_session.return_value = mock_channel

            session1 = mgr.create_session("test_session")
            session2 = mgr.get_session("test_session")

            assert session1 is session2

    def test_get_session_nonexistent(self):
        """测试获取不存在的会话"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class:
            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            session = mgr.get_session("nonexistent")

            assert session is None


class TestMultiSessionManagerClose:
    """测试关闭会话功能"""

    def test_close_session_success(self):
        """测试成功关闭会话"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with (
            patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class,
            patch.object(ShellSession, "__init__", return_value=None),
            patch.object(ShellSession, "initialize", return_value="$"),
            patch.object(ShellSession, "close", return_value=None),
        ):

            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            mock_channel = MagicMock()
            mock_channel.get_id.return_value = 1
            mock_transport.open_session.return_value = mock_channel

            mgr.create_session("test_session")

            result = mgr.close_session("test_session")

            assert result is True
            assert mgr.active_session_count == 0
            assert "test_session" not in mgr.list_sessions()

    def test_close_session_nonexistent(self):
        """测试关闭不存在的会话"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class:
            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            result = mgr.close_session("nonexistent")

            assert result is False

    def test_close_all_sessions(self):
        """测试关闭所有会话"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with (
            patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class,
            patch.object(ShellSession, "__init__", return_value=None),
            patch.object(ShellSession, "initialize", return_value="$"),
            patch.object(ShellSession, "close", return_value=None),
        ):

            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            for i in range(3):
                mock_channel = MagicMock()
                mock_channel.get_id.return_value = i + 1
                mock_transport.open_session.return_value = mock_channel
                mgr.create_session(f"session_{i}")

            closed_count = mgr.close_all_sessions()

            assert closed_count == 3
            assert mgr.active_session_count == 0


class TestMultiSessionManagerInfo:
    """测试会话信息功能"""

    def test_get_session_info(self):
        """测试获取会话信息"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with (
            patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class,
            patch.object(ShellSession, "__init__", return_value=None),
            patch.object(ShellSession, "initialize", return_value="$"),
        ):

            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            mock_channel = MagicMock()
            mock_channel.get_id.return_value = 1
            mock_transport.open_session.return_value = mock_channel

            mgr.create_session("test_session")

            info = mgr.get_session_info("test_session")

            assert info is not None
            assert info["session_id"] == "test_session"
            assert info["is_active"] is True
            assert "created_at" in info
            assert "command_count" in info

    def test_get_all_sessions_info(self):
        """测试获取所有会话信息"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with (
            patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class,
            patch.object(ShellSession, "__init__", return_value=None),
            patch.object(ShellSession, "initialize", return_value="$"),
        ):

            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            for i in range(3):
                mock_channel = MagicMock()
                mock_channel.get_id.return_value = i + 1
                mock_transport.open_session.return_value = mock_channel
                mgr.create_session(f"session_{i}")

            all_info = mgr.get_all_sessions_info()

            assert len(all_info) == 3
            for info in all_info:
                assert "session_id" in info
                assert "is_active" in info


class TestMultiSessionManagerActiveCount:
    """测试活跃会话计数"""

    def test_active_session_count_property(self):
        """测试活跃会话数属性"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )

        with (
            patch("src.backends.paramiko_backend.paramiko.SSHClient") as mock_client_class,
            patch.object(ShellSession, "__init__", return_value=None),
            patch.object(ShellSession, "initialize", return_value="$"),
            patch.object(ShellSession, "close", return_value=None),
        ):

            mock_client = MagicMock()
            mock_transport = MagicMock()
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True
            mock_client_class.return_value = mock_client

            conn = ConnectionManager(config)
            conn.connect()

            mgr = MultiSessionManager(conn, config)

            assert mgr.active_session_count == 0

            mock_channel = MagicMock()
            mock_channel.get_id.return_value = 1
            mock_transport.open_session.return_value = mock_channel

            mgr.create_session("session1")
            assert mgr.active_session_count == 1

            mock_channel2 = MagicMock()
            mock_channel2.get_id.return_value = 2
            mock_transport.open_session.return_value = mock_channel2

            mgr.create_session("session2")
            assert mgr.active_session_count == 2

            mgr.close_session("session1")
            assert mgr.active_session_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
