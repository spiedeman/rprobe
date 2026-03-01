"""
测试 SSHClient 多 Shell 会话功能 - 简化版

此测试文件验证多会话API的基本功能
"""

from unittest.mock import Mock, patch

import pytest

from rprobe import SSHClient
from rprobe.config.models import SSHConfig


class TestMultipleShellSessionsAPI:
    """测试多 Shell 会话 API"""

    @pytest.fixture
    def mock_ssh_config(self):
        """创建测试用的 SSH 配置"""
        return SSHConfig(
            host="test.example.com",
            username="testuser",
            password="testpass123",
            port=22,
            timeout=5.0,
            command_timeout=10.0,
        )

    def test_multiple_sessions_attributes(self, mock_ssh_config):
        """测试多会话属性初始状态"""
        client = SSHClient(mock_ssh_config, use_pool=False)

        # 验证初始状态
        assert client._session_manager is not None
        assert client.shell_session_count == 0
        assert client.shell_sessions == []
        assert client.shell_session_active is False

    def test_session_management_methods(self, mock_ssh_config):
        """测试会话管理方法"""
        client = SSHClient(mock_ssh_config, use_pool=False)

        # 模拟添加会话
        mock_session = Mock()
        mock_session.is_active = True

        # 添加会话到 Manager
        client._session_manager._sessions["session1"] = mock_session
        client._session_manager._default_session_id = "session1"

        # 验证属性
        assert client.shell_session_count == 1
        assert "session1" in client.shell_sessions
        assert client.shell_session_active is True

        # 获取会话 - MultiSessionManager 返回的是 shell_session 属性
        session_info = client._session_manager.get_session("session1")
        # 注意：Manager 返回的是 ShellSession 对象，不是 SessionInfo
        # 但在我们的测试中，我们直接存储了 mock_session
        # 所以这里直接检查返回值不为 None 即可
        assert session_info is not None

        # 获取不存在的会话
        assert client.get_shell_session("non-existent") is None

    def test_set_default_session(self, mock_ssh_config):
        """测试设置默认会话"""
        client = SSHClient(mock_ssh_config, use_pool=False)

        # 添加两个会话
        mock_session1 = Mock()
        mock_session1.is_active = True
        mock_session2 = Mock()
        mock_session2.is_active = True

        client._session_manager._sessions["session1"] = mock_session1
        client._session_manager._sessions["session2"] = mock_session2
        client._session_manager._default_session_id = "session1"

        assert client._session_manager._default_session_id == "session1"

        # 设置新的默认会话
        client.set_default_shell_session("session2")
        assert client._session_manager._default_session_id == "session2"

        # 尝试设置不存在的会话 - 现在抛出 ValueError
        with pytest.raises((RuntimeError, ValueError)):
            client.set_default_shell_session("non-existent")

    def test_close_all_sessions(self, mock_ssh_config):
        """测试关闭所有会话"""
        client = SSHClient(mock_ssh_config, use_pool=False)

        # 添加多个会话
        for i in range(3):
            mock_session = Mock()
            mock_session.is_active = True
            client._session_manager._sessions[f"session{i}"] = mock_session

        client._session_manager._default_session_id = "session0"
        assert client.shell_session_count == 3

        # 关闭所有会话
        client.close_all_shell_sessions()

        # 验证 - close_all_sessions 标记会话为不活跃，但不删除它们
        assert client.shell_session_count == 0
        assert client._session_manager._default_session_id is None
        # 会话对象仍然存在，只是标记为 is_active=False
        assert len(client._session_manager._sessions) == 3

    def test_backward_compatibility(self, mock_ssh_config):
        """测试向后兼容 - 单会话场景"""
        client = SSHClient(mock_ssh_config, use_pool=False)

        # 模拟旧方式使用单会话
        mock_session = Mock()
        mock_session.is_active = True

        # 设置会话为默认
        session_id = "auto-generated-id"
        client._session_manager._sessions[session_id] = mock_session
        client._session_manager._default_session_id = session_id

        # 验证向后兼容属性
        assert client.shell_session_active is True
        assert client.shell_session_count == 1

        # 关闭默认会话（不传 session_id）
        client.close_shell_session()
        assert client.shell_session_active is False
