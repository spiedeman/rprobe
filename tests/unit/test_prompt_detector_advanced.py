"""
Prompt Detector 模块单元测试 - 补充测试
测试提示符检测的各种场景
"""

import pytest

from rprobe.patterns import (
    PromptDetector,
    PromptLearningStrategy,
    DefaultLearningStrategy,
    PromptMatchResult,
)
from rprobe.patterns import PromptCategory


class TestPromptLearningStrategy:
    """测试提示符学习策略"""

    def test_default_learning_strategy_basic(self):
        """测试默认学习策略基本功能"""
        strategy = DefaultLearningStrategy()

        pattern = strategy.learn("user@host:~$")

        assert pattern is not None
        assert pattern.match("user@host:~$")

    def test_default_learning_strategy_with_spaces(self):
        """测试学习带空格的提示符"""
        strategy = DefaultLearningStrategy()

        pattern = strategy.learn("user@host:~$ ")

        assert pattern is not None
        # 学习的模式应该匹配带或不带空格的字符串
        assert pattern.match("user@host:~$ ")
        assert pattern.match("user@host:~$  ")  # 多个空格也能匹配

    def test_default_learning_strategy_empty(self):
        """测试空提示符学习"""
        strategy = DefaultLearningStrategy()

        pattern = strategy.learn("")

        assert pattern is None

    def test_default_learning_strategy_special_chars(self):
        """测试特殊字符的学习"""
        strategy = DefaultLearningStrategy()

        pattern = strategy.learn("❯❯")

        assert pattern is not None


class TestPromptMatchResult:
    """测试提示符匹配结果"""

    def test_match_result_bool_conversion(self):
        """测试匹配结果的布尔转换"""
        match = PromptMatchResult(is_match=True, matched_text="test")
        no_match = PromptMatchResult(is_match=False)

        assert bool(match) is True
        assert bool(no_match) is False

    def test_match_result_representation(self):
        """测试匹配结果的字符串表示"""
        match = PromptMatchResult(
            is_match=True,
            matched_text="user@host:~$",
            pattern_name="unix_traditional",
            category=PromptCategory.UNIX_TRADITIONAL,
        )

        repr_str = repr(match)

        assert "True" in repr_str
        assert "user@host:~$" in repr_str


class TestPromptDetectorAdvanced:
    """提示符检测器高级测试"""

    def test_detector_with_custom_learning_strategy(self):
        """测试使用自定义学习策略"""

        class CustomStrategy(PromptLearningStrategy):
            def learn(self, prompt):
                return None  # 不学习

        detector = PromptDetector(learning_strategy=CustomStrategy())
        detector.detect("user@host:~$", learn=True)

        assert detector.learned_pattern is None

    def test_detector_disable_learning(self):
        """测试禁用学习功能"""
        detector = PromptDetector(enable_learning=False)

        detector.detect("user@host:~$", learn=True)

        assert detector.learned_pattern is None

    def test_match_line_with_learned_pattern_priority(self):
        """测试学习模式的优先级"""
        detector = PromptDetector()

        # 先检测一个提示符并学习
        detector.detect("custom@prompt:~$", learn=True)

        # 再匹配相同模式
        result = detector.match_line("custom@prompt:~$")

        assert result.is_match is True
        assert result.is_learned is True

    def test_detect_empty_lines(self):
        """测试检测空行"""
        detector = PromptDetector()

        # 只有空行的输出
        result = detector.detect("\n\n\n")

        assert result == "#"  # 默认提示符

    def test_detect_with_ansi_codes(self):
        """测试带 ANSI 代码的检测"""
        detector = PromptDetector()

        # 带颜色代码的提示符
        output = "\x1b[32muser@host\x1b[0m:\x1b[34m~\x1b[0m$"
        result = detector.detect(output)

        assert result == "user@host:~$"

    def test_clean_output_without_prompt(self):
        """测试没有提示符时的清理"""
        detector = PromptDetector()

        output = "ls\nfile1.txt\nfile2.txt\n"
        cleaned = detector.clean_output(output, "ls")

        assert "file1.txt" in cleaned
        assert "file2.txt" in cleaned

    def test_clean_output_with_only_prompt(self):
        """测试只有提示符的清理"""
        detector = PromptDetector()
        detector._last_prompt = "user@host:~$"

        output = "ls\nuser@host:~$"
        cleaned = detector.clean_output(output, "ls")

        assert "ls" not in cleaned
        assert "user@host:~$" not in cleaned

    def test_clean_output_preserves_formatting(self):
        """测试清理保留格式"""
        detector = PromptDetector()
        detector._last_prompt = "user@host:~$"

        output = "ls\nfile1.txt\nfile2.txt\nuser@host:~$"
        cleaned = detector.clean_output(output, "ls")

        lines = cleaned.split("\n")
        assert len(lines) == 2
        assert lines[0] == "file1.txt"
        assert lines[1] == "file2.txt"

    def test_statistics_after_multiple_matches(self):
        """测试多次匹配后的统计"""
        detector = PromptDetector()

        # 进行多次匹配
        detector.is_prompt_line("user@host:~$")  # Unix
        detector.is_prompt_line("root@server:#")  # Unix
        detector.is_prompt_line("C:\\>")  # Windows
        detector.is_prompt_line("not a prompt")  # 不匹配

        stats = detector.get_statistics()

        assert stats["total_matches"] == 3
        assert len(stats["category_distribution"]) >= 2

    def test_statistics_with_learning(self):
        """测试学习后的统计"""
        detector = PromptDetector()

        # 检测并学习
        detector.detect("custom@pattern:~$", learn=True)
        detector.is_prompt_line("custom@pattern:~$")  # 使用学习的模式

        stats = detector.get_statistics()

        assert stats["has_learned_pattern"] is True
        assert stats["learned_matches"] == 1

    def test_reset_clears_history(self):
        """测试重置清除历史"""
        detector = PromptDetector()

        detector.is_prompt_line("user@host:~$")
        detector.detect("custom:~$", learn=True)

        detector.reset()

        assert detector.learned_pattern is None
        assert detector.last_prompt is None
        assert len(detector.match_history) == 0

    def test_detect_various_unix_formats(self):
        """测试检测各种 Unix 格式"""
        detector = PromptDetector()

        formats = [
            ("user@host:~$", "user@host:~$"),
            ("[user@host ~]$", "[user@host ~]$"),
            ("root@server:/#", "root@server:/#"),
            ("~>", "~>"),
        ]

        for input_prompt, expected in formats:
            result = detector.detect(input_prompt)
            assert result == expected, f"Failed for {input_prompt}"

    def test_detect_various_windows_formats(self):
        """测试检测各种 Windows 格式"""
        detector = PromptDetector()

        formats = [
            ("C:\\>", "C:\\>"),
            ("C:\\Windows>", "C:\\Windows>"),
            ("PS C:\\>", "PS C:\\>"),
        ]

        for input_prompt, expected in formats:
            result = detector.detect(input_prompt)
            assert result == expected, f"Failed for {input_prompt}"


class TestPromptDetectorUnicode:
    """测试 Unicode 提示符检测"""

    def test_detect_unicode_arrows(self):
        """测试检测 Unicode 箭头"""
        detector = PromptDetector()

        arrows = ["❯", "➜", "→", "▶", "▸"]

        for arrow in arrows:
            result = detector.detect(arrow)
            assert result == arrow

    def test_detect_unicode_with_context(self):
        """测试带上下文的 Unicode"""
        detector = PromptDetector()

        output = "Some text\nMore text\n❯"
        result = detector.detect(output)

        assert result == "❯"

    def test_detect_double_unicode(self):
        """测试双 Unicode 符号"""
        detector = PromptDetector()

        result = detector.detect("❯❯")

        assert result == "❯❯"

    def test_detect_unicode_with_space(self):
        """测试带空格的 Unicode"""
        detector = PromptDetector()

        result = detector.detect(" ❯")

        # 应该能检测到，可能是 " ❯" 或 "❯"
        assert "❯" in result


class TestPromptDetectorEdgeCases:
    """提示符检测器边界情况"""

    def test_detect_multiline_with_prompt_in_middle(self):
        """测试中间有提示符的多行"""
        detector = PromptDetector()

        # 提示符在中间，应该返回最后一个
        output = "user@host:~/dir1$\nSome output\nuser@host:~/dir2$"
        result = detector.detect(output)

        assert result == "user@host:~/dir2$"

    def test_detect_only_whitespace(self):
        """测试只有空白字符"""
        detector = PromptDetector()

        result = detector.detect("   \n\t\n  ")

        assert result == "#"  # 默认提示符

    def test_detect_fallback_to_last_line(self):
        """测试回退到最后一行"""
        detector = PromptDetector()

        # 不匹配任何已知模式的文本
        output = "Just some text\nThat doesn't look like a prompt"
        result = detector.detect(output)

        assert result == "That doesn't look like a prompt"

    def test_match_line_empty_string(self):
        """测试匹配空字符串"""
        detector = PromptDetector()

        result = detector.match_line("")

        assert result.is_match is False

    def test_match_line_whitespace_only(self):
        """测试匹配仅空白字符"""
        detector = PromptDetector()

        result = detector.match_line("   \t\n  ")

        assert result.is_match is False

    def test_clean_output_empty(self):
        """测试清理空输出"""
        detector = PromptDetector()

        cleaned = detector.clean_output("", "ls")

        assert cleaned == ""

    def test_clean_output_only_command(self):
        """测试只有命令的输出"""
        detector = PromptDetector()

        cleaned = detector.clean_output("ls", "ls")

        assert cleaned == ""
