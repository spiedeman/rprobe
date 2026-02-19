"""
ANSI Cleaner 模块单元测试
测试 ANSI 控制字符清理的各种便捷方法
"""

import pytest

from src.utils.ansi_cleaner import ANSICleaner, ANSICleanupRule, ANSISequenceType, strip_ansi


class TestANSICleanerBasic:
    """测试基本的 ANSI 清理功能"""

    def test_clean_empty_string(self):
        """测试空字符串清理"""
        assert ANSICleaner.clean("") == ""

    def test_clean_no_ansi(self):
        """测试不含 ANSI 的普通文本"""
        text = "Hello World"
        assert ANSICleaner.clean(text) == text

    def test_clean_color_codes(self):
        """测试颜色代码清理"""
        colored = "\x1b[32mGreen\x1b[0m"
        assert ANSICleaner.clean(colored) == "Green"

    def test_clean_osc_sequences(self):
        """测试 OSC 序列清理"""
        # 终端标题设置序列
        osc_text = "\x1b]0;Terminal Title\x07prompt"
        assert ANSICleaner.clean(osc_text) == "prompt"

    def test_clean_bell_character(self):
        """测试响铃字符清理"""
        text = "Hello\x07World"
        assert ANSICleaner.clean(text) == "HelloWorld"

    def test_clean_carriage_return(self):
        """测试回车符清理"""
        text = "line1\r\nline2"
        assert ANSICleaner.clean(text) == "line1\nline2"


class TestANSICleanerKeepNewlines:
    """测试保留换行的清理功能"""

    def test_clean_keep_newlines_basic(self):
        """测试基本保留换行"""
        text = "\x1b[32mLine1\nLine2\x1b[0m"
        result = ANSICleaner.clean_keep_newlines(text)
        assert result == "Line1\nLine2"

    def test_clean_keep_newlines_multiple(self):
        """测试多行保留"""
        text = "\x1b[34mA\nB\nC\x1b[0m"
        result = ANSICleaner.clean_keep_newlines(text)
        assert result == "A\nB\nC"

    def test_clean_keep_newlines_with_cr(self):
        """测试保留换行同时清理回车"""
        text = "Line1\r\nLine2\r\nLine3"
        result = ANSICleaner.clean_keep_newlines(text)
        # 应该先替换换行为占位符，再清理
        assert "\n" in result


class TestANSICleanerForDisplay:
    """测试用于显示的清理功能"""

    def test_clean_for_display_no_truncation(self):
        """测试无需截断的情况"""
        text = "\x1b[32mHello\x1b[0m World"
        result = ANSICleaner.clean_for_display(text, max_length=50)
        assert result == "Hello World"

    def test_clean_for_display_with_truncation(self):
        """测试需要截断的情况"""
        text = "\x1b[32mThis is a very long text\x1b[0m"
        result = ANSICleaner.clean_for_display(text, max_length=10)
        assert result == "This is..."
        assert len(result) == 10

    def test_clean_for_display_no_max_length(self):
        """测试不设置最大长度"""
        text = "\x1b[31mRed text\x1b[0m"
        result = ANSICleaner.clean_for_display(text)
        assert result == "Red text"


class TestANSICleanerHasANSI:
    """测试 ANSI 检测功能"""

    def test_has_ansi_with_color(self):
        """测试包含颜色代码"""
        assert ANSICleaner.has_ansi("\x1b[32mGreen\x1b[0m") is True

    def test_has_ansi_with_osc(self):
        """测试包含 OSC 序列"""
        assert ANSICleaner.has_ansi("\x1b]0;Title\x07") is True

    def test_has_ansi_with_bell(self):
        """测试包含响铃字符"""
        assert ANSICleaner.has_ansi("Hello\x07") is True

    def test_has_ansi_with_cr(self):
        """测试包含回车符"""
        assert ANSICleaner.has_ansi("Line\r") is True

    def test_has_ansi_no_ansi(self):
        """测试不含 ANSI"""
        assert ANSICleaner.has_ansi("Plain text") is False

    def test_has_ansi_empty(self):
        """测试空字符串"""
        assert ANSICleaner.has_ansi("") is False


class TestANSICleanerLength:
    """测试 ANSI 长度计算"""

    def test_strip_ansi_length_simple(self):
        """测试简单文本长度"""
        assert ANSICleaner.strip_ansi_length("Hello") == 5

    def test_strip_ansi_length_with_color(self):
        """测试带颜色代码的长度"""
        colored = "\x1b[32mHi\x1b[0m"
        assert ANSICleaner.strip_ansi_length(colored) == 2

    def test_strip_ansi_length_complex(self):
        """测试复杂 ANSI 序列的长度"""
        text = "\x1b[1;31;40mRed\x1b[0m \x1b[32mGreen\x1b[0m"
        assert ANSICleaner.strip_ansi_length(text) == 9  # "Red Green"


class TestANSICleanerCustomRules:
    """测试自定义清理规则"""

    def test_add_custom_rule(self):
        """测试添加自定义规则"""
        cleaner = ANSICleaner()
        custom_rule = ANSICleanupRule(
            name="custom_test",
            description="测试规则",
            pattern=__import__("re").compile(r"test_\d+"),
            replacement="[REMOVED]",
        )

        cleaner.add_rule(custom_rule)
        result = cleaner.clean_with_rules("test_123 text")
        assert "[REMOVED]" in result

    def test_custom_rule_chain(self):
        """测试规则链式调用"""
        cleaner = ANSICleaner()

        rule1 = ANSICleanupRule(
            name="rule1",
            description="规则1",
            pattern=__import__("re").compile(r"ABC"),
            replacement="X",
        )

        rule2 = ANSICleanupRule(
            name="rule2",
            description="规则2",
            pattern=__import__("re").compile(r"XYZ"),
            replacement="Y",
        )

        cleaner.add_rule(rule1).add_rule(rule2)  # 链式调用
        result = cleaner.clean_with_rules("ABC and XYZ")
        assert result == "X and Y"

    def test_custom_rule_without_default(self):
        """测试不使用默认规则的自定义清理"""
        cleaner = ANSICleaner()
        custom_rule = ANSICleanupRule(
            name="custom_only",
            description="仅自定义规则",
            pattern=__import__("re").compile(r"delete_this"),
            replacement="",
        )

        cleaner.add_rule(custom_rule)
        text = "delete_this \x1b[32mkeep this\x1b[0m"

        # 不包含默认规则时，ANSI 代码应该保留
        result = cleaner.clean_with_rules(text, include_default=False)
        assert "delete_this" not in result
        assert "\x1b[32m" in result  # ANSI 代码应该还在


class TestANSISequenceType:
    """测试 ANSI 序列类型定义"""

    def test_csi_pattern(self):
        """测试 CSI 序列模式"""
        pattern = ANSISequenceType.CSI
        assert pattern.match("\x1b[32m")
        assert pattern.match("\x1b[1;31;40m")
        assert pattern.match("\x1b[0m")
        assert not pattern.match("normal text")

    def test_osc_pattern(self):
        """测试 OSC 序列模式"""
        pattern = ANSISequenceType.OSC
        assert pattern.match("\x1b]0;title\x07")
        assert pattern.match("\x1b]2;window\x1b\\")

    def test_8bit_csi_pattern(self):
        """测试 8-bit CSI 模式"""
        pattern = ANSISequenceType.CSI_8BIT
        # 0x9b 是 CSI 的 8-bit 表示
        assert pattern.match("\x9b32m")


class TestStripANSIFunction:
    """测试便捷函数"""

    def test_strip_ansi_function(self):
        """测试 strip_ansi 便捷函数"""
        colored = "\x1b[31mRed\x1b[0m \x1b[32mGreen\x1b[0m"
        result = strip_ansi(colored)
        assert result == "Red Green"

    def test_strip_ansi_empty(self):
        """测试空字符串"""
        assert strip_ansi("") == ""
