"""
ANSI控制字符清理模块
提供终端控制序列的识别和清理功能

设计原则：
1. 使用类方法组织不同类型的清理规则
2. 提供清晰的文档说明每种序列的格式
3. 支持链式调用和自定义清理流程
"""

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Pattern


@dataclass(frozen=True)
class ANSICleanupRule:
    """
    ANSI清理规则定义

    Attributes:
        name: 规则名称
        description: 规则描述
        pattern: 正则表达式模式
        replacement: 替换字符串（默认为空字符串）
    """

    name: str
    description: str
    pattern: Pattern
    replacement: str = ""


class ANSISequenceType:
    """
    ANSI序列类型定义

    提供各种ANSI控制序列的正则表达式模式
    """

    # OSC (Operating System Command) 序列
    # 格式: ESC ] <参数> <终止符>
    # 终止符可以是 BEL (\x07) 或 ST (\x1b\\)
    OSC = re.compile(r"\x1b\][0-9;]*(?:[^\x07\x1b]*)(?:\x07|\x1b\\)")

    # CSI (Control Sequence Introducer) 序列
    # 格式: ESC [ <参数> <最终字节>
    # 最终字节范围: @-~
    CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

    # FE (Format Effector) 序列
    # 格式: ESC <字母> (A-Z, \, _, ^等)
    FE = re.compile(r"\x1b[@-Z\\-_]")

    # 8-bit CSI (不使用ESC [的CSI)
    # 直接字符: 0x9b
    CSI_8BIT = re.compile(r"\x9b[0-?]*[ -/]*[@-~]")

    # 单个控制字符
    BELL = "\x07"  # 响铃
    BACKSPACE = "\x08"  # 退格
    TAB = "\x09"  # 制表符
    LINEFEED = "\x0a"  # 换行
    FORMFEED = "\x0c"  # 换页
    CARRIAGE_RETURN = "\x0d"  # 回车


class ANSICleaner:
    """
    ANSI控制字符清理器

    提供完整的ANSI控制序列清理功能

    Example:
        # 基本使用
        clean_text = ANSICleaner.clean(colored_text)

        # 自定义清理规则
        cleaner = ANSICleaner()
        cleaner.add_rule(custom_rule)
        clean_text = cleaner.clean_with_rules(dirty_text)
    """

    # 默认清理规则
    DEFAULT_RULES: List[ANSICleanupRule] = [
        ANSICleanupRule(
            name="osc_sequences", description="OSC序列(终端标题等)", pattern=ANSISequenceType.OSC
        ),
        ANSICleanupRule(
            name="csi_sequences", description="CSI序列(颜色、光标等)", pattern=ANSISequenceType.CSI
        ),
        ANSICleanupRule(name="fe_sequences", description="FE序列", pattern=ANSISequenceType.FE),
        ANSICleanupRule(
            name="csi_8bit", description="8-bit CSI", pattern=ANSISequenceType.CSI_8BIT
        ),
    ]

    def __init__(self):
        """初始化清理器"""
        self._custom_rules: List[ANSICleanupRule] = []

    def add_rule(self, rule: ANSICleanupRule) -> "ANSICleaner":
        """
        添加自定义清理规则

        Args:
            rule: 清理规则

        Returns:
            self，支持链式调用
        """
        self._custom_rules.append(rule)
        return self

    @classmethod
    def clean(cls, text: str) -> str:
        """
        清理文本中的所有ANSI控制序列

        Args:
            text: 包含ANSI序列的文本

        Returns:
            str: 清理后的文本
        """
        if not text:
            return text

        # 应用默认规则
        for rule in cls.DEFAULT_RULES:
            text = rule.pattern.sub(rule.replacement, text)

        # 清理单个控制字符
        text = cls._clean_control_chars(text)

        return text

    @classmethod
    def clean_keep_newlines(cls, text: str) -> str:
        """
        清理ANSI序列但保留所有换行符

        Args:
            text: 包含ANSI序列的文本

        Returns:
            str: 清理后的文本（保留换行）
        """
        if not text:
            return text

        # 先将换行符替换为占位符
        text = text.replace("\n", "\x00NEWLINE\x00")
        text = cls.clean(text)
        text = text.replace("\x00NEWLINE\x00", "\n")

        return text

    @classmethod
    def clean_for_display(cls, text: str, max_length: Optional[int] = None) -> str:
        """
        清理并截断文本用于显示

        Args:
            text: 包含ANSI序列的文本
            max_length: 最大显示长度

        Returns:
            str: 清理并可能截断后的文本
        """
        text = cls.clean(text)

        if max_length and len(text) > max_length:
            text = text[: max_length - 3] + "..."

        return text

    def clean_with_rules(self, text: str, include_default: bool = True) -> str:
        """
        使用自定义规则清理文本

        Args:
            text: 包含ANSI序列的文本
            include_default: 是否包含默认规则

        Returns:
            str: 清理后的文本
        """
        if not text:
            return text

        rules = []
        if include_default:
            rules.extend(self.DEFAULT_RULES)
        rules.extend(self._custom_rules)

        for rule in rules:
            text = rule.pattern.sub(rule.replacement, text)

        text = self._clean_control_chars(text)

        return text

    @staticmethod
    def _clean_control_chars(text: str) -> str:
        """
        清理单个控制字符

        Args:
            text: 输入文本

        Returns:
            str: 清理后的文本
        """
        # 移除响铃字符
        text = text.replace(ANSISequenceType.BELL, "")

        # 移除回车符（保留换行）
        text = text.replace(ANSISequenceType.CARRIAGE_RETURN, "")

        return text

    @classmethod
    def has_ansi(cls, text: str) -> bool:
        """
        检查文本是否包含ANSI序列

        Args:
            text: 要检查的文本

        Returns:
            bool: 是否包含ANSI序列
        """
        if not text:
            return False

        for rule in cls.DEFAULT_RULES:
            if rule.pattern.search(text):
                return True

        # 检查单个控制字符
        control_chars = [ANSISequenceType.BELL, ANSISequenceType.CARRIAGE_RETURN]

        for char in control_chars:
            if char in text:
                return True

        return False

    @classmethod
    def strip_ansi_length(cls, text: str) -> int:
        """
        获取去除ANSI后的文本长度

        Args:
            text: 输入文本

        Returns:
            int: 清理后的长度
        """
        return len(cls.clean(text))


# 保持向后兼容性的便捷函数
def strip_ansi(text: str) -> str:
    """清理ANSI控制字符的便捷函数"""
    return ANSICleaner.clean(text)
