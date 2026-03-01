"""
提示符模式定义模块
提供结构化的提示符模式定义和构建功能

设计原则：
1. 单一职责：每个模式类只负责一种类型的提示符
2. 开闭原则：通过继承扩展新的提示符类型，而非修改现有代码
3. 可读性优先：使用描述性名称和文档字符串
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Set


class PromptCategory(Enum):
    """提示符类别枚举"""

    UNIX_TRADITIONAL = auto()  # Unix/Linux 传统格式
    UNIX_BRACKETED = auto()  # 带方括号的格式
    WINDOWS_CMD = auto()  # Windows CMD
    WINDOWS_POWERSHELL = auto()  # Windows PowerShell
    MODERN_SHELL = auto()  # 现代Shell (Fish, Starship等)
    GIT_BRANCH = auto()  # 带Git分支信息
    TIME_BASED = auto()  # 带时间信息
    SIMPLE = auto()  # 简单格式


# Unicode提示符字符集 - 按类别组织
UNICODE_ARROWS: Set[str] = {
    "❯",
    "❱",
    "▶",
    "▸",
    "►",
    "▷",
    "→",
    "⇒",
    "⇨",
    "➜",
    "➤",
    "➥",
    "➔",
    "➙",
    "➛",
    "➝",
    "➞",
    "➟",
    "➠",
    "➡",
    "➢",
    "➣",
    "➦",
    "➧",
    "➨",
    "➩",
    "➪",
    "➫",
    "➬",
    "➭",
    "➮",
    "➯",
    "➱",
    "➲",
    "➳",
    "➴",
    "➵",
    "➶",
    "➷",
    "➸",
    "➹",
    "➺",
    "➻",
    "➼",
    "➽",
    "➾",
    "➿",
}

TRADITIONAL_MARKS: Set[str] = {"$", "#", "%", ">", ":", "~"}

ALL_PROMPT_CHARS: str = "".join(UNICODE_ARROWS | TRADITIONAL_MARKS)


@dataclass(frozen=True)
class PromptPattern:
    """
    提示符模式定义

    Attributes:
        name: 模式名称（用于调试和日志）
        category: 提示符类别
        pattern: 正则表达式模式
        examples: 示例提示符列表（用于测试和文档）
        description: 模式描述
    """

    name: str
    category: PromptCategory
    pattern: re.Pattern
    examples: List[str]
    description: str


class PromptPatternBuilder:
    """
    提示符模式构建器

    提供构建各种提示符模式的工厂方法
    """

    @staticmethod
    def unix_traditional() -> PromptPattern:
        """Unix/Linux 传统格式: user@host:~$"""
        return PromptPattern(
            name="unix_traditional",
            category=PromptCategory.UNIX_TRADITIONAL,
            pattern=re.compile(r"^[\w\-]+@[\w\-]+:[\w\/\.~\-]*[\$#%]\s*$"),
            examples=["user@host:~$", "root@server:/#", "admin@my-host:/home/user$"],
            description="标准Unix/Linux格式: username@hostname:path$",
        )

    @staticmethod
    def unix_bracketed() -> PromptPattern:
        """带方括号的格式: [user@host ~]$"""
        return PromptPattern(
            name="unix_bracketed",
            category=PromptCategory.UNIX_BRACKETED,
            pattern=re.compile(r"\[?[\w\-]+@[\w\-]+\s+[\w\/\.~\-]+\]?[\$#%]\s*$"),
            examples=["[user@host ~]$", "[root@server /]#", "[admin@web /var]$"],
            description="带方括号的Unix格式",
        )

    @staticmethod
    def unix_simplified() -> PromptPattern:
        """简化格式: user@host$"""
        return PromptPattern(
            name="unix_simplified",
            category=PromptCategory.UNIX_TRADITIONAL,
            pattern=re.compile(r"^[\w\-]+@[\w\-]+[\$#%]\s*$"),
            examples=["user@host$", "root@server#"],
            description="简化Unix格式，不含路径",
        )

    @staticmethod
    def root_prompt() -> PromptPattern:
        """Root用户提示符"""
        return PromptPattern(
            name="root_prompt",
            category=PromptCategory.UNIX_TRADITIONAL,
            pattern=re.compile(r"^root@[\w\-]+.*#[\s]*$"),
            examples=["root@host:~#", "root@server:#"],
            description="Root用户提示符",
        )

    @staticmethod
    def fish_shell() -> PromptPattern:
        """Fish Shell格式"""
        return PromptPattern(
            name="fish_shell",
            category=PromptCategory.MODERN_SHELL,
            pattern=re.compile(r"^[\w\-]+@[\w\-]+:[\w\/\.~\-]*>\s*$"),
            examples=["user@host:~>", "root@server:/etc>"],
            description="Fish Shell使用>作为提示符",
        )

    @staticmethod
    def fish_simplified() -> PromptPattern:
        """Fish Shell简化格式"""
        return PromptPattern(
            name="fish_simplified",
            category=PromptCategory.SIMPLE,
            pattern=re.compile(r"^~>\s*$"),
            examples=["~>"],
            description="Fish Shell简化格式",
        )

    @staticmethod
    def windows_cmd() -> PromptPattern:
        """Windows CMD格式"""
        return PromptPattern(
            name="windows_cmd",
            category=PromptCategory.WINDOWS_CMD,
            pattern=re.compile(r"^[A-Za-z]:\\.*>\s*$"),
            examples=["C:\\>", "C:\\Windows\\System32>", "D:\\Projects>"],
            description="Windows CMD提示符",
        )

    @staticmethod
    def windows_powershell() -> PromptPattern:
        """Windows PowerShell格式"""
        return PromptPattern(
            name="windows_powershell",
            category=PromptCategory.WINDOWS_POWERSHELL,
            pattern=re.compile(r"^PS\s+(?:[A-Za-z]:|\\\\).*?>\s*$"),
            examples=["PS C:\\>", "PS C:\\Windows>", "PS \\\\server\\share>"],
            description="Windows PowerShell提示符",
        )

    @staticmethod
    def powershell_core() -> PromptPattern:
        """PowerShell Core格式"""
        return PromptPattern(
            name="powershell_core",
            category=PromptCategory.WINDOWS_POWERSHELL,
            pattern=re.compile(r"\[?[\w\-]+@[\w\-]+\]?:?\s*PS\s+[A-Za-z]:\\.*>\s*$"),
            examples=["[user@host]: PS C:\\>", "[admin@server]: PS C:\\Windows>"],
            description="PowerShell Core带SSH远程信息",
        )

    @staticmethod
    def git_branch() -> PromptPattern:
        """带Git分支信息的提示符"""
        return PromptPattern(
            name="git_branch",
            category=PromptCategory.GIT_BRANCH,
            pattern=re.compile(r"^[\w\-]+@[\w\-]+:[\w\/\.~\-]*\s*\([^)]*\)[\$#%]\s*$"),
            examples=[
                "user@host:~/project (main)$",
                "user@host:~/code (feature-branch)$",
                "root@server:/repo (v1.0)#",
            ],
            description="Zsh等Shell带Git分支信息",
        )

    @staticmethod
    def time_based() -> PromptPattern:
        """带时间信息的提示符"""
        return PromptPattern(
            name="time_based",
            category=PromptCategory.TIME_BASED,
            pattern=re.compile(r"\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*[\w\-]+@[\w\-]+.*[\$#%]\s*$"),
            examples=[
                "[10:30] user@host:~$",
                "[14:25:30] root@server:#",
                "[23:59:59] admin@web-server:/var/log$",
            ],
            description="带时间的自定义PS1",
        )

    @staticmethod
    def traditional_marks() -> PromptPattern:
        """传统提示符标记"""
        return PromptPattern(
            name="traditional_marks",
            category=PromptCategory.SIMPLE,
            pattern=re.compile(r"^[\$#%>:~]\s*$"),
            examples=["$", "#", ">", "~"],
            description="传统纯符号提示符",
        )

    @staticmethod
    def unicode_arrow_single() -> PromptPattern:
        """单个Unicode箭头"""
        return PromptPattern(
            name="unicode_arrow_single",
            category=PromptCategory.MODERN_SHELL,
            pattern=re.compile(f"^[❯❱▶▸►▷→⇒⇨➜➤➥➔➙➛➝➞➟➠➡➢➣➦➧➨➩➪➫➬➭➮➯➱➲➳➴➵➶➷➸➹➺➻➼➽➾➿\\$#%>:~]\\s*$"),
            examples=["❯", "➜", "→"],
            description="单个Unicode箭头提示符",
        )

    @staticmethod
    def unicode_arrow_double() -> PromptPattern:
        """双Unicode箭头组合"""
        return PromptPattern(
            name="unicode_arrow_double",
            category=PromptCategory.MODERN_SHELL,
            pattern=re.compile(f"^[❯❱▶▸►▷→⇒⇨➜➤➥]{{1,3}}\\s*$"),
            examples=["❯❯", "▶▶", "→→", "➜➜"],
            description="双Unicode箭头组合（如Starship）",
        )

    @staticmethod
    def unicode_with_space() -> PromptPattern:
        """带空格的Unicode提示符"""
        return PromptPattern(
            name="unicode_with_space",
            category=PromptCategory.MODERN_SHELL,
            pattern=re.compile(f"\\s+[❯❱▶▸►▷→⇒⇨➜➤➥➔➙➛➝➞➟➠➡➢➣➦➧➨➩➪➫➬➭➮➯➱➲➳➴➵➶➷➸➹➺➻➼➽➾➿]\\s*$"),
            examples=[" ❯", " ➜", " →"],
            description="带前导空格的Unicode提示符",
        )

    @classmethod
    def build_all(cls) -> List[PromptPattern]:
        """构建所有默认提示符模式"""
        return [
            cls.unix_traditional(),
            cls.unix_bracketed(),
            cls.unix_simplified(),
            cls.root_prompt(),
            cls.fish_shell(),
            cls.fish_simplified(),
            cls.windows_cmd(),
            cls.windows_powershell(),
            cls.powershell_core(),
            cls.git_branch(),
            cls.time_based(),
            cls.traditional_marks(),
            cls.unicode_arrow_single(),
            cls.unicode_arrow_double(),
            cls.unicode_with_space(),
        ]


# 便捷访问：默认提示符模式列表
DEFAULT_PROMPT_PATTERNS: List[PromptPattern] = PromptPatternBuilder.build_all()
