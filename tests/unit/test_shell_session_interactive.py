"""
ShellSession 交互式功能测试
测试 enter_interactive, exit_interactive, execute_interactive
"""

import socket
from unittest.mock import Mock, patch, MagicMock

import pytest
import paramiko

from rprobe.config.models import SSHConfig
from rprobe.session import ShellSession
from rprobe.patterns import PromptDetector


@pytest.fixture
def mock_config():
    """创建测试配置"""
    return SSHConfig(
        host="test.example.com", username="testuser", password="testpass", command_timeout=10.0
    )


@pytest.fixture
def mock_channel():
    """创建模拟 channel"""
    channel = Mock(spec=paramiko.Channel)
    channel.closed = False
    channel.recv_ready.return_value = True
    channel.recv.return_value = b""
    return channel


class TestEnterInteractive:
    """测试 enter_interactive 方法"""

    def test_enter_interactive_basic(self, mock_channel, mock_config):
        """测试基本进入交互式程序"""
        session = ShellSession(mock_channel, mock_config)

        # 模拟等待输出返回
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            output = session.enter_interactive("python")

        assert session.is_in_interactive is True
        assert session.current_interactive_program == "python"
        assert ">>>" in session._prompt_detector.learned_prompts

    def test_enter_interactive_with_custom_prompt(self, mock_channel, mock_config):
        """测试进入交互式程序时指定自定义提示符"""
        session = ShellSession(mock_channel, mock_config)

        with patch.object(session, "_wait_for_output", return_value="mytool> "):
            output = session.enter_interactive("mytool", prompt="mytool>")

        assert "mytool>" in session._prompt_detector.learned_prompts
        assert session._prompt_detector.last_prompt == "mytool>"

    def test_enter_interactive_with_learn_prompts(self, mock_channel, mock_config):
        """测试进入交互式程序时学习额外提示符"""
        session = ShellSession(mock_channel, mock_config)

        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python", learn_prompts=["...", ">>> "])

        assert ">>>" in session._prompt_detector.learned_prompts
        assert "..." in session._prompt_detector.learned_prompts

    def test_enter_interactive_with_both_prompt_and_learn_prompts(self, mock_channel, mock_config):
        """测试同时指定主提示符和学习额外提示符"""
        session = ShellSession(mock_channel, mock_config)

        with patch.object(session, "_wait_for_output", return_value="main> "):
            session.enter_interactive(
                "custom", prompt="main>", learn_prompts=["secondary>", "...>"]
            )

        assert "main>" in session._prompt_detector.learned_prompts
        assert "secondary>" in session._prompt_detector.learned_prompts
        assert "...>" in session._prompt_detector.learned_prompts
        # 主提示符应该是 last_prompt
        assert session._prompt_detector.last_prompt == "main>"

    def test_enter_interactive_duplicate_prompt_skipped(self, mock_channel, mock_config):
        """测试重复提示符被跳过"""
        session = ShellSession(mock_channel, mock_config)

        with patch.object(session, "_wait_for_output", return_value=">>> "):
            # 主提示符和学习的提示符重复
            session.enter_interactive(
                "python", prompt=">>>", learn_prompts=[">>>", "..."]  # >>> 应该被跳过
            )

        # 应该只学习 >>> 一次
        assert session._prompt_detector.learned_prompts.count(">>>") == 1

    def test_enter_interactive_saves_context(self, mock_channel, mock_config):
        """测试进入交互式程序时保存上下文"""
        session = ShellSession(mock_channel, mock_config)

        # 先设置一些学习状态
        session._prompt_detector.learn_prompt("shell$")
        session._prompt_detector._last_prompt = "shell$"

        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        # 验证保存了上下文
        assert session._saved_context is not None
        assert "shell$" in session._saved_context["learned_prompts"]

    def test_enter_interactive_resets_learned(self, mock_channel, mock_config):
        """测试进入交互式程序前重置学习状态"""
        session = ShellSession(mock_channel, mock_config)

        # 先学习一些提示符
        session._prompt_detector.learn_prompt("old_prompt")

        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        # 旧的应该被清除，新的应该被学习
        assert "old_prompt" not in session._prompt_detector.learned_prompts
        assert ">>>" in session._prompt_detector.learned_prompts

    def test_enter_interactive_sends_command(self, mock_channel, mock_config):
        """测试发送进入命令"""
        session = ShellSession(mock_channel, mock_config)

        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        mock_channel.send.assert_called_with(b"python\n")

    def test_enter_interactive_when_inactive(self, mock_channel, mock_config):
        """测试在会话不活跃时进入交互式程序"""
        session = ShellSession(mock_channel, mock_config)
        mock_channel.closed = True

        with pytest.raises(RuntimeError, match="Shell 会话未激活"):
            session.enter_interactive("python")

    def test_enter_interactive_known_programs(self, mock_channel, mock_config):
        """测试进入已知的交互式程序"""
        session = ShellSession(mock_channel, mock_config)

        # 测试 scapy
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("scapy")
        assert ">>>" in session._prompt_detector.learned_prompts

        # 测试 ipython
        session._prompt_detector.reset_learned_only()
        with patch.object(session, "_wait_for_output", return_value="In [1]: "):
            session.enter_interactive("ipython")
        assert "In [" in session._prompt_detector.learned_prompts


class TestExitInteractive:
    """测试 exit_interactive 方法"""

    def test_exit_interactive_basic(self, mock_channel, mock_config):
        """测试基本退出交互式程序"""
        session = ShellSession(mock_channel, mock_config)

        # 先进入交互式程序
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        # 模拟退出输出
        with patch.object(session, "_wait_for_output", return_value="user@host:~$"):
            output = session.exit_interactive()

        assert session.is_in_interactive is False
        assert session.current_interactive_program is None
        mock_channel.send.assert_called_with(b"exit()\n")

    def test_exit_interactive_restores_context(self, mock_channel, mock_config):
        """测试退出时恢复上下文"""
        session = ShellSession(mock_channel, mock_config)

        # 先学习 shell 提示符
        session._prompt_detector.learn_prompt("shell$")
        session._prompt_detector._last_prompt = "shell$"

        # 进入 python
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        # 学习 python 提示符
        assert ">>>" in session._prompt_detector.learned_prompts

        # 退出
        with patch.object(session, "_wait_for_output", return_value="shell$"):
            session.exit_interactive()

        # 验证恢复了上下文
        assert "shell$" in session._prompt_detector.learned_prompts
        assert ">>>" not in session._prompt_detector.learned_prompts
        assert session._prompt_detector.last_prompt == "shell$"

    def test_exit_interactive_custom_command(self, mock_channel, mock_config):
        """测试使用自定义退出命令"""
        session = ShellSession(mock_channel, mock_config)

        # 进入
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        # 使用自定义退出命令
        with patch.object(session, "_wait_for_output", return_value=""):
            session.exit_interactive("quit()")

        mock_channel.send.assert_called_with(b"quit()\n")

    def test_exit_interactive_when_not_in_interactive(self, mock_channel, mock_config):
        """测试不在交互式程序中时退出"""
        session = ShellSession(mock_channel, mock_config)

        # 不应该抛出异常，只是返回空字符串
        output = session.exit_interactive()
        assert output == ""

    def test_exit_interactive_when_inactive(self, mock_channel, mock_config):
        """测试在会话不活跃时退出"""
        session = ShellSession(mock_channel, mock_config)

        # 先进入
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        mock_channel.closed = True

        with pytest.raises(RuntimeError, match="Shell 会话未激活"):
            session.exit_interactive()


class TestExecuteInteractive:
    """测试 execute_interactive 方法"""

    def test_execute_interactive_basic(self, mock_channel, mock_config):
        """测试在交互式程序中执行命令"""
        session = ShellSession(mock_channel, mock_config)

        # 进入 python
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        # 执行命令
        with patch.object(session, "_wait_for_output", return_value="4\n>>> "):
            output = session.execute_interactive("2+2")

        mock_channel.send.assert_called_with(b"2+2\n")
        assert "4" in output

    def test_execute_interactive_learns_new_prompt(self, mock_channel, mock_config):
        """测试执行命令时学习新的提示符"""
        session = ShellSession(mock_channel, mock_config)

        # 进入 python
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        # 执行命令后输出包含不同的提示符
        with patch.object(session, "_wait_for_output", return_value="result\n... "):
            session.execute_interactive("if True:")

        # 应该学习了次级提示符
        assert "..." in session._prompt_detector.learned_prompts

    def test_execute_interactive_when_not_in_interactive(self, mock_channel, mock_config):
        """测试不在交互式程序中时执行命令"""
        session = ShellSession(mock_channel, mock_config)

        with pytest.raises(RuntimeError, match="当前不在交互式程序中"):
            session.execute_interactive("print('hello')")

    def test_execute_interactive_when_inactive(self, mock_channel, mock_config):
        """测试在会话不活跃时执行命令"""
        session = ShellSession(mock_channel, mock_config)

        # 先进入
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        mock_channel.closed = True

        with pytest.raises(RuntimeError, match="Shell 会话未激活"):
            session.execute_interactive("print('hello')")


class TestInteractiveProperties:
    """测试交互式属性"""

    def test_is_in_interactive_property(self, mock_channel, mock_config):
        """测试 is_in_interactive 属性"""
        session = ShellSession(mock_channel, mock_config)

        assert session.is_in_interactive is False

        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        assert session.is_in_interactive is True

        with patch.object(session, "_wait_for_output", return_value="$"):
            session.exit_interactive()

        assert session.is_in_interactive is False

    def test_current_interactive_program_property(self, mock_channel, mock_config):
        """测试 current_interactive_program 属性"""
        session = ShellSession(mock_channel, mock_config)

        assert session.current_interactive_program is None

        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        assert session.current_interactive_program == "python"

        with patch.object(session, "_wait_for_output", return_value="$"):
            session.exit_interactive()

        assert session.current_interactive_program is None


class TestInteractiveWorkflow:
    """测试完整的交互式工作流"""

    def test_full_scapy_workflow(self, mock_channel, mock_config):
        """测试完整的 scapy 工作流"""
        session = ShellSession(mock_channel, mock_config)

        # 进入 scapy
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("scapy")

        assert session.is_in_interactive is True
        assert ">>>" in session._prompt_detector.learned_prompts

        # 执行几个命令
        with patch.object(session, "_wait_for_output", return_value="IP\n>>> "):
            output = session.execute_interactive("IP()")

        with patch.object(session, "_wait_for_output", return_value="TCP\n>>> "):
            output = session.execute_interactive("TCP()")

        # 退出 scapy
        with patch.object(session, "_wait_for_output", return_value="user@host:~$"):
            session.exit_interactive()

        assert session.is_in_interactive is False

    def test_nested_interactive_not_supported(self, mock_channel, mock_config):
        """测试不支持嵌套交互式程序（保存单个上下文）"""
        session = ShellSession(mock_channel, mock_config)

        # 进入第一层
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        assert session.is_in_interactive is True
        assert session.current_interactive_program == "python"

        # 尝试进入第二层（会覆盖第一层上下文）
        with patch.object(session, "_wait_for_output", return_value="In [1]: "):
            session.enter_interactive("ipython")

        # 第二层应该覆盖第一层
        assert session.is_in_interactive is True
        assert session.current_interactive_program == "ipython"

        # 退出后，由于没有保存嵌套上下文，应该回到非交互状态
        with patch.object(session, "_wait_for_output", return_value="shell$"):
            session.exit_interactive()

        # 退出后不在交互式程序中
        assert session.is_in_interactive is False
        assert session.current_interactive_program is None

    def test_multiple_enter_exit_cycles(self, mock_channel, mock_config):
        """测试多次进入退出循环"""
        session = ShellSession(mock_channel, mock_config)

        # 先学习 shell 提示符
        session._prompt_detector.learn_prompt("shell$")
        session._prompt_detector._last_prompt = "shell$"

        # 第一次进入 python
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("python")

        with patch.object(session, "_wait_for_output", return_value="shell$"):
            session.exit_interactive()

        # 验证恢复了 shell 提示符
        assert "shell$" in session._prompt_detector.learned_prompts

        # 第二次进入 scapy
        with patch.object(session, "_wait_for_output", return_value=">>> "):
            session.enter_interactive("scapy")

        assert session.is_in_interactive is True

        with patch.object(session, "_wait_for_output", return_value="shell$"):
            session.exit_interactive()

        # 再次验证恢复
        assert session.is_in_interactive is False
        assert "shell$" in session._prompt_detector.learned_prompts


class TestEnterInteractiveWithCustomProgram:
    """测试使用自定义程序名"""

    def test_enter_unknown_program(self, mock_channel, mock_config):
        """测试进入未知的交互式程序"""
        session = ShellSession(mock_channel, mock_config)

        # 未知的程序不会预学习任何提示符
        with patch.object(session, "_wait_for_output", return_value="custom> "):
            session.enter_interactive("unknown_program")

        # 应该没有预学习的提示符（除非从输出中检测）
        assert session.is_in_interactive is True

    def test_enter_program_with_custom_prompt_only(self, mock_channel, mock_config):
        """测试只指定自定义提示符，不使用预定义程序"""
        session = ShellSession(mock_channel, mock_config)

        with patch.object(session, "_wait_for_output", return_value="custom> "):
            session.enter_interactive("my_custom_tool", prompt="custom>", learn_prompts=["sub>"])

        assert "custom>" in session._prompt_detector.learned_prompts
        assert "sub>" in session._prompt_detector.learned_prompts
        assert session._prompt_detector.last_prompt == "custom>"
