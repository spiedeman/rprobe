"""
MultiSessionManager 扩展功能单元测试

测试扩展后的 MultiSessionManager 功能，包括：
- 连接池/直连模式支持
- 默认会话管理
- 向后兼容性
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import threading

from rprobe.core.connection import MultiSessionManager, SessionInfo, ConnectionManager
from rprobe.config.models import SSHConfig


@pytest.fixture
def mock_config():
    """创建 Mock 配置"""
    return SSHConfig(
        host="test.example.com",
        username="test",
        password="test",
        timeout=30.0,
    )


@pytest.fixture
def mock_connection():
    """创建 Mock 连接"""
    conn = Mock(spec=ConnectionManager)
    conn.open_channel = Mock(return_value=Mock())
    return conn


@pytest.fixture
def mock_pool():
    """创建 Mock 连接池"""
    pool = Mock()
    mock_conn = Mock()
    mock_conn.open_channel = Mock(return_value=Mock())
    pool.get_connection = Mock(return_value=mock_conn)
    return pool


class TestMultiSessionManagerInit:
    """测试 MultiSessionManager 初始化"""

    def test_init_with_connection(self, mock_connection, mock_config):
        """测试直连模式初始化"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        assert manager._connection == mock_connection
        assert manager._config == mock_config
        assert manager._use_pool is False
        assert manager._pool is None
        assert manager._default_session_id is None

    def test_init_with_pool(self, mock_pool, mock_config):
        """测试连接池模式初始化"""
        manager = MultiSessionManager(
            config=mock_config,
            use_pool=True,
            pool=mock_pool,
        )

        assert manager._pool == mock_pool
        assert manager._config == mock_config
        assert manager._use_pool is True
        assert manager._connection is None

    def test_init_pool_without_pool_raises_error(self, mock_config):
        """测试使用池模式但不提供 pool 应该报错"""
        with pytest.raises(ValueError, match="使用连接池模式时必须提供 pool 参数"):
            MultiSessionManager(
                config=mock_config,
                use_pool=True,
            )

    def test_init_direct_without_connection_raises_error(self, mock_config):
        """测试直连模式但不提供 connection 应该报错"""
        with pytest.raises(ValueError, match="直连模式时必须提供 connection 参数"):
            MultiSessionManager(
                config=mock_config,
                use_pool=False,
            )


class TestMultiSessionManagerCreateSession:
    """测试创建会话功能"""

    @patch("rprobe.session.shell_session.ShellSession")
    def test_create_session_with_connection(
        self, mock_shell_session_class, mock_connection, mock_config
    ):
        """测试直连模式创建会话"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        mock_session = Mock()
        mock_session.initialize = Mock()
        mock_shell_session_class.return_value = mock_session

        session = manager.create_session(session_id="test_session")

        assert session == mock_session
        mock_connection.open_channel.assert_called_once()
        mock_session.initialize.assert_called_once()
        assert "test_session" in manager._sessions

    @patch("rprobe.session.shell_session.ShellSession")
    def test_create_session_with_pool(self, mock_shell_session_class, mock_pool, mock_config):
        """测试连接池模式创建会话"""
        manager = MultiSessionManager(
            config=mock_config,
            use_pool=True,
            pool=mock_pool,
        )

        mock_session = Mock()
        mock_session.initialize = Mock()
        mock_shell_session_class.return_value = mock_session

        session = manager.create_session(session_id="pool_session")

        assert session == mock_session
        mock_pool.get_connection.assert_called_once()
        mock_session.initialize.assert_called_once()
        assert "pool_session" in manager._sessions

    @patch("rprobe.session.shell_session.ShellSession")
    def test_create_session_auto_id(self, mock_shell_session_class, mock_connection, mock_config):
        """测试自动生成会话 ID"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        mock_session = Mock()
        mock_session.initialize = Mock()
        mock_shell_session_class.return_value = mock_session

        session = manager.create_session()

        # 应该生成类似 "session_1" 的 ID
        assert manager._session_counter == 1
        assert "session_1" in manager._sessions

    @patch("rprobe.session.shell_session.ShellSession")
    def test_create_session_duplicate_id_raises_error(
        self, mock_shell_session_class, mock_connection, mock_config
    ):
        """测试重复会话 ID 应该报错"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        mock_session = Mock()
        mock_session.initialize = Mock()
        mock_shell_session_class.return_value = mock_session

        # 创建第一个会话
        manager.create_session(session_id="dup_id")

        # 创建相同 ID 应该报错
        with pytest.raises(ValueError, match="Session 'dup_id' already exists"):
            manager.create_session(session_id="dup_id")


class TestMultiSessionManagerDefaultSession:
    """测试默认会话功能"""

    @patch("rprobe.session.shell_session.ShellSession")
    def test_set_default_session(self, mock_shell_session_class, mock_connection, mock_config):
        """测试设置默认会话"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        mock_session = Mock()
        mock_session.initialize = Mock()
        mock_shell_session_class.return_value = mock_session

        # 创建会话
        manager.create_session(session_id="session1")

        # 设置为默认
        manager.set_default_session("session1")

        assert manager.get_default_session_id() == "session1"
        assert manager.get_default_session() == mock_session

    @patch("rprobe.session.shell_session.ShellSession")
    def test_create_session_auto_set_default(
        self, mock_shell_session_class, mock_connection, mock_config
    ):
        """测试创建第一个会话自动设为默认"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        mock_session = Mock()
        mock_session.initialize = Mock()
        mock_shell_session_class.return_value = mock_session

        # 创建第一个会话，应该自动设为默认
        manager.create_session(session_id="first")

        assert manager.get_default_session_id() == "first"

    @patch("rprobe.session.shell_session.ShellSession")
    def test_create_session_set_as_default_parameter(
        self, mock_shell_session_class, mock_connection, mock_config
    ):
        """测试 set_as_default 参数"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        mock_session = Mock()
        mock_session.initialize = Mock()
        mock_shell_session_class.return_value = mock_session

        # 第一个会话，由于没有默认会话，即使 set_as_default=False 也会被设为默认
        manager.create_session(session_id="first", set_as_default=False)
        # 当没有默认会话时，第一个会话会被自动设为默认
        assert manager.get_default_session_id() == "first"

        # 创建第二个会话，明确设为默认
        manager.create_session(session_id="second", set_as_default=True)
        assert manager.get_default_session_id() == "second"

    @patch("rprobe.session.shell_session.ShellSession")
    def test_close_session_updates_default(
        self, mock_shell_session_class, mock_connection, mock_config
    ):
        """测试关闭默认会话时更新默认"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        mock_session1 = Mock()
        mock_session1.initialize = Mock()
        mock_session2 = Mock()
        mock_session2.initialize = Mock()

        mock_shell_session_class.side_effect = [mock_session1, mock_session2]

        # 创建两个会话
        manager.create_session(session_id="session1")
        manager.create_session(session_id="session2")

        # 默认应该是 session1
        assert manager.get_default_session_id() == "session1"

        # 关闭 session1，默认应该自动切换到 session2
        manager.close_session("session1")

        assert manager.get_default_session_id() == "session2"

    def test_set_nonexistent_session_as_default_raises_error(self, mock_connection, mock_config):
        """测试设置不存在的会话为默认应该报错"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        with pytest.raises(ValueError, match="Session 'nonexistent' does not exist"):
            manager.set_default_session("nonexistent")

    def test_clear_default_session(self, mock_connection, mock_config):
        """测试清除默认会话"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        with patch("rprobe.session.shell_session.ShellSession") as mock_class:
            mock_session = Mock()
            mock_session.initialize = Mock()
            mock_class.return_value = mock_session

            manager.create_session(session_id="session1")
            assert manager.get_default_session_id() is not None

            manager.clear_default_session()
            assert manager.get_default_session_id() is None


class TestMultiSessionManagerBackwardCompatibility:
    """测试向后兼容性"""

    @patch("rprobe.session.shell_session.ShellSession")
    def test_old_api_still_works(self, mock_shell_session_class):
        """测试旧的 API 调用方式仍然有效"""
        config = SSHConfig(
            host="test.example.com",
            username="test",
            password="test",
        )
        connection = Mock(spec=ConnectionManager)
        connection.open_channel = Mock(return_value=Mock())

        # 旧的方式：只传 connection 和 config
        manager = MultiSessionManager(connection=connection, config=config)

        mock_session = Mock()
        mock_session.initialize = Mock()
        mock_shell_session_class.return_value = mock_session

        # 旧的调用方式：不传 use_pool 和 pool
        session = manager.create_session(session_id="test")

        assert session == mock_session
        assert "test" in manager._sessions

    def test_get_session_returns_none_for_nonexistent(self, mock_connection, mock_config):
        """测试获取不存在的会话返回 None"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        assert manager.get_session("nonexistent") is None

    def test_get_default_session_returns_none_when_no_default(self, mock_connection, mock_config):
        """测试没有默认会话时返回 None"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        assert manager.get_default_session() is None


class TestMultiSessionManagerThreadSafety:
    """测试线程安全性"""

    @patch("rprobe.session.shell_session.ShellSession")
    def test_concurrent_create_session(
        self, mock_shell_session_class, mock_connection, mock_config
    ):
        """测试并发创建会话"""
        manager = MultiSessionManager(
            connection=mock_connection,
            config=mock_config,
            use_pool=False,
        )

        mock_session = Mock()
        mock_session.initialize = Mock()
        mock_shell_session_class.return_value = mock_session

        sessions_created = []

        def create_session():
            session = manager.create_session()
            sessions_created.append(session)

        # 并发创建 10 个会话
        threads = [threading.Thread(target=create_session) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 应该成功创建 10 个不同的会话
        assert len(sessions_created) == 10
        assert manager.active_session_count == 10
        # 检查所有会话 ID 都不同
        session_ids = list(manager._sessions.keys())
        assert len(session_ids) == len(set(session_ids))  # 确保 ID 唯一
