"""
Shell Session 模块简化补充测试
只测试简单可靠的场景
"""

import socket
from unittest.mock import Mock

import pytest

from rprobe.session import ShellSession
from rprobe.config.models import SSHConfig
from rprobe.patterns import PromptDetector


class TestShellSessionBasic:
    """ShellSession 基础测试"""

    def test_init_creates_default_detector(self):
        """测试初始化创建默认检测器"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        mock_channel = Mock()

        session = ShellSession(mock_channel, config)

        assert session._channel == mock_channel
        assert session._config == config
        assert isinstance(session._prompt_detector, PromptDetector)

    def test_init_with_custom_detector(self):
        """测试使用自定义检测器初始化"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        mock_channel = Mock()
        custom_detector = PromptDetector()

        session = ShellSession(mock_channel, config, custom_detector)

        assert session._prompt_detector == custom_detector

    def test_is_active_when_open(self):
        """测试打开状态的会话"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        mock_channel = Mock()
        mock_channel.closed = False

        session = ShellSession(mock_channel, config)

        assert session.is_active is True

    def test_is_active_when_channel_closed(self):
        """测试channel关闭的会话"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        mock_channel = Mock()
        mock_channel.closed = True

        session = ShellSession(mock_channel, config)

        assert session.is_active is False

    def test_is_active_after_close(self):
        """测试调用close后的状态"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        mock_channel = Mock()

        session = ShellSession(mock_channel, config)
        session.close()

        assert session.is_active is False

    def test_close_idempotent(self):
        """测试关闭是幂等的"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        mock_channel = Mock()

        session = ShellSession(mock_channel, config)
        session.close()
        session.close()  # 再次关闭不应出错

        assert session.is_active is False

    def test_prompt_property_initially_none(self):
        """测试初始prompt为None"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        mock_channel = Mock()

        session = ShellSession(mock_channel, config)

        assert session.prompt is None

    def test_prompt_property_after_set(self):
        """测试设置prompt后的属性"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        mock_channel = Mock()

        session = ShellSession(mock_channel, config)
        session._prompt_detector._last_prompt = "user@host:~$"

        assert session.prompt == "user@host:~$"


class TestShellSessionInitialize:
    """测试会话初始化"""

    def test_initialize_basic(self):
        """测试基本初始化"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", command_timeout=0.1
        )
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"user@host:~$ "

        session = ShellSession(mock_channel, config)
        prompt = session.initialize(timeout=0.1)

        assert "user@host:~$" in prompt
        mock_channel.get_pty.assert_called_once()
        mock_channel.invoke_shell.assert_called_once()

    def test_initialize_uses_default_timeout(self):
        """测试使用默认超时初始化"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", command_timeout=0.1
        )
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"$ "

        session = ShellSession(mock_channel, config)
        session.initialize()  # 不传timeout

        # 验证使用了config中的timeout
        mock_channel.settimeout.assert_called_with(0.1)

    def test_initialize_learns_prompt(self):
        """测试初始化学习提示符"""
        config = SSHConfig(
            host="test.example.com", username="user", password="pass", command_timeout=0.1
        )
        mock_channel = Mock()
        mock_channel.recv_ready.side_effect = [True, False]
        mock_channel.recv.return_value = b"custom@host:~$ "

        session = ShellSession(mock_channel, config)
        session.initialize(timeout=0.1)

        # 验证学习了提示符模式
        assert session._prompt_detector.learned_pattern is not None


class TestShellSessionClose:
    """测试会话关闭"""

    def test_close_calls_channel_close(self):
        """测试关闭调用channel关闭"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        mock_channel = Mock()

        session = ShellSession(mock_channel, config)
        session.close()

        mock_channel.close.assert_called_once()

    def test_close_resets_detector(self):
        """测试关闭重置检测器"""
        config = SSHConfig(host="test.example.com", username="user", password="pass")
        mock_channel = Mock()

        session = ShellSession(mock_channel, config)
        session._prompt_detector._last_prompt = "test"
        import re

        session._prompt_detector._learned_patterns.append(re.compile(r"test"))
        session._prompt_detector._learned_prompts.append("test")

        session.close()

        assert session._prompt_detector._last_prompt is None
        assert len(session._prompt_detector._learned_patterns) == 0
        assert len(session._prompt_detector._learned_prompts) == 0
