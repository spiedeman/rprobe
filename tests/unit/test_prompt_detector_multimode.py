"""
PromptDetector 多模式学习功能测试
测试多模式学习、上下文管理和提示符变化检测
"""

import re
from unittest.mock import Mock, patch

import pytest

from src.patterns import PromptDetector, DefaultLearningStrategy


class TestMultiPatternLearning:
    """测试多模式学习功能"""

    def test_learn_multiple_prompts(self):
        """测试学习多个提示符"""
        detector = PromptDetector()

        # 学习多个提示符
        assert detector.learn_prompt(">>>") is True
        assert detector.learn_prompt("...") is True
        assert detector.learn_prompt("In [1]:") is True

        # 验证都学习了
        assert len(detector.learned_patterns) == 3
        assert len(detector.learned_prompts) == 3
        assert ">>>" in detector.learned_prompts
        assert "..." in detector.learned_prompts
        assert "In [1]:" in detector.learned_prompts

    def test_learn_duplicate_prompt(self):
        """测试学习重复提示符"""
        detector = PromptDetector()

        # 第一次学习
        assert detector.learn_prompt(">>>") is True
        # 重复学习应该返回 True（已存在）
        assert detector.learn_prompt(">>>") is True
        # 仍然只有一个
        assert len(detector.learned_patterns) == 1

    def test_learn_prompt_does_not_change_position(self):
        """测试重复学习提示符不会改变位置（显式学习不更新LRU）"""
        detector = PromptDetector(max_learned_patterns=3)

        detector.learn_prompt("first")
        detector.learn_prompt("second")
        detector.learn_prompt("third")

        # 重复学习第一个，显式学习不会改变位置
        result = detector.learn_prompt("first")

        # 返回 True 表示已存在，但位置不变
        assert result is True
        assert detector.learned_prompts[0] == "first"
        assert detector.learned_prompts[1] == "second"
        assert detector.learned_prompts[2] == "third"

    def test_max_learned_patterns_limit(self):
        """测试学习模式数量限制"""
        detector = PromptDetector(max_learned_patterns=3)

        # 学习超过限制的提示符
        detector.learn_prompt("prompt1")
        detector.learn_prompt("prompt2")
        detector.learn_prompt("prompt3")
        detector.learn_prompt("prompt4")  # 这应该移除最早学习的

        assert len(detector.learned_patterns) == 3
        assert len(detector.learned_prompts) == 3
        # 最早学习的应该被移除
        assert "prompt1" not in detector.learned_prompts
        assert "prompt4" in detector.learned_prompts

    def test_learn_empty_prompt(self):
        """测试学习空提示符"""
        detector = PromptDetector()

        assert detector.learn_prompt("") is False
        assert len(detector.learned_patterns) == 0

    def test_learn_prompt_with_learning_disabled(self):
        """测试禁用学习时学习提示符"""
        detector = PromptDetector(enable_learning=False)

        assert detector.learn_prompt(">>>") is False
        assert len(detector.learned_patterns) == 0

    def test_has_learned_prompt(self):
        """测试检查是否已学习提示符"""
        detector = PromptDetector()

        assert detector.has_learned_prompt(">>>") is False

        detector.learn_prompt(">>>")
        assert detector.has_learned_prompt(">>>") is True
        assert detector.has_learned_prompt("...") is False


class TestContextManagement:
    """测试上下文管理功能"""

    def test_save_context(self):
        """测试保存上下文"""
        detector = PromptDetector()
        detector.learn_prompt(">>>")
        detector.learn_prompt("...")
        detector._last_prompt = ">>>"

        context = detector.save_context()

        assert "learned_patterns" in context
        assert "learned_prompts" in context
        assert "last_prompt" in context
        assert "timestamp" in context
        assert context["last_prompt"] == ">>>"
        assert len(context["learned_prompts"]) == 2

    def test_restore_context(self):
        """测试恢复上下文"""
        detector = PromptDetector()

        # 学习一些提示符
        detector.learn_prompt("old_prompt1")
        detector.learn_prompt("old_prompt2")
        detector._last_prompt = "old_prompt1"

        # 保存上下文
        context = detector.save_context()

        # 学习新的提示符
        detector.learn_prompt("new_prompt")
        detector._last_prompt = "new_prompt"

        # 恢复上下文
        detector.restore_context(context)

        # 验证恢复
        assert detector.last_prompt == "old_prompt1"
        assert "old_prompt1" in detector.learned_prompts
        assert "old_prompt2" in detector.learned_prompts
        assert "new_prompt" not in detector.learned_prompts

    def test_restore_latest_context(self):
        """测试恢复最近保存的上下文（不传参数）"""
        detector = PromptDetector()

        detector.learn_prompt("prompt1")
        detector.save_context()

        detector.learn_prompt("prompt2")
        detector.save_context()

        # 学习新的
        detector.learn_prompt("prompt3")

        # 恢复最近的（应该是 prompt2）
        detector.restore_context()

        assert "prompt2" in detector.learned_prompts
        assert "prompt3" not in detector.learned_prompts

    def test_restore_context_empty_stack(self):
        """测试没有上下文时恢复"""
        detector = PromptDetector()

        # 不应该抛出异常
        detector.restore_context()
        assert detector.last_prompt is None

    def test_context_stack_depth(self):
        """测试上下文栈深度"""
        detector = PromptDetector()

        detector.learn_prompt("p1")
        detector.save_context()

        detector.learn_prompt("p2")
        detector.save_context()

        detector.learn_prompt("p3")
        detector.save_context()

        # 恢复3次
        detector.restore_context()
        detector.restore_context()
        detector.restore_context()

        # 第4次恢复应该无影响
        detector.restore_context()
        assert True  # 没有异常


class TestPromptChangeDetection:
    """测试提示符变化检测"""

    def test_detect_prompt_change_with_change(self):
        """测试检测到提示符变化"""
        detector = PromptDetector()

        old_prompt = "user@host:~$"
        # 新的输出包含不同的提示符
        new_output = "some output\nIn [1]:"

        new_prompt = detector.detect_prompt_change(old_prompt, new_output)

        assert new_prompt is not None
        assert new_prompt == "In [1]:"

    def test_detect_prompt_change_no_change(self):
        """测试没有提示符变化"""
        detector = PromptDetector()

        old_prompt = "user@host:~$"
        new_output = "some output\nuser@host:~$"

        new_prompt = detector.detect_prompt_change(old_prompt, new_output)

        # 提示符没有变化，应该返回 None
        assert new_prompt is None

    def test_match_line_with_multiple_learned_patterns(self):
        """测试多个学习模式的匹配"""
        detector = PromptDetector()

        # 学习多个提示符
        detector.learn_prompt(">>>")
        detector.learn_prompt("...")
        detector.learn_prompt("CUSTOM_PROMPT_123")

        # 应该能匹配所有学习的提示符
        assert detector.is_prompt_line(">>>") is True
        assert detector.is_prompt_line("...") is True
        assert detector.is_prompt_line("CUSTOM_PROMPT_123") is True
        # 使用一个不太可能匹配内置模式的字符串
        assert detector.is_prompt_line("XYZ_UNKNOWN_999") is False


class TestResetLearnedOnly:
    """测试只重置学习状态"""

    def test_reset_learned_only(self):
        """测试只重置学习状态"""
        detector = PromptDetector()

        detector.learn_prompt(">>>")
        detector.learn_prompt("...")
        detector._last_prompt = ">>>"
        detector._match_history.append(Mock())

        detector.reset_learned_only()

        assert len(detector.learned_patterns) == 0
        assert len(detector.learned_prompts) == 0
        # last_prompt 和 match_history 应该保留
        assert detector.last_prompt == ">>>"
        assert len(detector.match_history) == 1

    def test_reset_all(self):
        """测试完全重置"""
        detector = PromptDetector()

        detector.learn_prompt(">>>")
        detector._last_prompt = ">>>"
        detector._match_history.append(Mock())
        detector.save_context()

        detector.reset()

        assert len(detector.learned_patterns) == 0
        assert detector.last_prompt is None
        assert len(detector.match_history) == 0
        assert len(detector._context_stack) == 0


class TestLearnedPatternProperty:
    """测试 learned_pattern 属性（向后兼容）"""

    def test_learned_pattern_returns_last(self):
        """测试 learned_pattern 返回最后学习的模式"""
        detector = PromptDetector()

        assert detector.learned_pattern is None

        detector.learn_prompt("first")
        assert detector.learned_pattern is not None

        detector.learn_prompt("second")
        # 应该返回最后一个
        pattern = detector.learned_pattern
        assert pattern.search("second") is not None

    def test_learned_patterns_returns_copy(self):
        """测试 learned_patterns 返回副本"""
        detector = PromptDetector()

        detector.learn_prompt(">>>")
        patterns = detector.learned_patterns

        # 修改返回的列表不应影响原对象
        import re

        fake_pattern = re.compile("fake")
        patterns.append(fake_pattern)
        assert len(detector.learned_patterns) == 1


class TestStatisticsWithMultiPattern:
    """测试多模式下的统计信息"""

    def test_statistics_with_multiple_learned(self):
        """测试多学习模式的统计信息"""
        detector = PromptDetector()

        detector.learn_prompt(">>>")
        detector.learn_prompt("...")

        # 匹配学习的模式
        detector.match_line(">>>")
        detector.match_line("...")
        detector.match_line("user@host:~$")  # 标准模式

        stats = detector.get_statistics()

        assert stats["total_matches"] == 3
        assert stats["learned_matches"] == 2
        assert stats["has_learned_pattern"] is True
        assert stats["learned_patterns_count"] == 2


class TestIntegrationScenarios:
    """集成测试场景"""

    def test_scapy_workflow(self):
        """测试 scapy 工作流场景"""
        detector = PromptDetector()

        # 初始 shell 提示符
        detector.detect("user@host:~$", learn=True)
        assert detector.last_prompt == "user@host:~$"

        # 进入 scapy 前保存上下文
        context = detector.save_context()
        detector.reset_learned_only()

        # 学习 scapy 提示符
        detector.learn_prompt(">>>")
        detector.learn_prompt("...")

        # 检测 scapy 提示符
        assert detector.is_prompt_line(">>>") is True
        assert detector.is_prompt_line("...") is True

        # 退出 scapy，恢复上下文
        detector.restore_context(context)
        assert detector.last_prompt == "user@host:~$"

    def test_ipython_workflow(self):
        """测试 IPython 工作流场景"""
        detector = PromptDetector()

        # 保存初始状态
        detector.detect("user@host:~$", learn=True)
        context = detector.save_context()
        detector.reset_learned_only()

        # 学习 IPython 提示符（不包括带前导空格的次级提示符）
        detector.learn_prompt("In [1]:")
        detector.learn_prompt("...:")  # 简化版本，不带前导空格
        detector.learn_prompt("Out[1]:")

        # 在 IPython 中 - 验证能匹配学习的提示符
        assert detector.is_prompt_line("In [1]:") is True
        assert detector.is_prompt_line("...:") is True
        assert detector.is_prompt_line("Out[1]:") is True
        # 注意：学习的模式是精确匹配，不会自动匹配 In [10]:
        # 因为转义后的正则不会将 [1] 视为可变的数字

        # 退出恢复
        detector.restore_context(context)
        assert detector.is_prompt_line("user@host:~$") is True

    def test_multiple_interactive_programs(self):
        """测试连续进入多个交互式程序"""
        detector = PromptDetector()

        # 第一层：Python
        detector.learn_prompt(">>>")
        python_context = detector.save_context()

        # 第二层：IPython（嵌套）
        detector.reset_learned_only()
        detector.learn_prompt("In [1]:")
        ipython_context = detector.save_context()

        # 第三层：Scapy
        detector.reset_learned_only()
        detector.learn_prompt(">>>")

        assert detector.is_prompt_line(">>>") is True

        # 逐层退出
        detector.restore_context(ipython_context)
        assert detector.is_prompt_line("In [1]:") is True

        detector.restore_context(python_context)
        assert detector.is_prompt_line(">>>") is True
