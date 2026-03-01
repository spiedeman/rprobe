"""
Patterns模块

提供提示符模式定义和检测功能。
"""

from rprobe.patterns.prompt_patterns import PromptPattern, PromptPatternBuilder, PromptCategory
from rprobe.patterns.prompt_detector import (
    PromptDetector,
    PromptLearningStrategy,
    DefaultLearningStrategy,
    PromptMatchResult,
)

__all__ = [
    "PromptPattern",
    "PromptPatternBuilder",
    "PromptCategory",
    "PromptDetector",
    "PromptLearningStrategy",
    "DefaultLearningStrategy",
    "PromptMatchResult",
]
