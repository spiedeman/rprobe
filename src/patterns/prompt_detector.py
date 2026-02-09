"""
提示符检测模块（重构版）
提供提示符检测和输出清理功能

设计原则：
1. 依赖注入：通过构造函数接收配置和依赖
2. 策略模式：支持自定义提示符匹配策略
3. 观察模式：支持学习新的提示符模式
"""
import logging
import re
import time
from typing import List, Optional

from src.patterns.prompt_patterns import PromptPattern, PromptPatternBuilder, PromptCategory
from src.utils.ansi_cleaner import ANSICleaner


logger = logging.getLogger(__name__)


class PromptLearningStrategy:
    """
    提示符学习策略接口
    
    定义如何学习新的提示符模式
    """
    
    def learn(self, prompt: str) -> Optional[re.Pattern]:
        """
        从检测到的提示符学习模式
        
        Args:
            prompt: 检测到的提示符
            
        Returns:
            Optional[re.Pattern]: 学习的模式，如果不学习则返回None
        """
        raise NotImplementedError


class DefaultLearningStrategy(PromptLearningStrategy):
    """
    默认提示符学习策略
    
    将提示符转换为正则表达式模式，允许灵活的空白字符匹配
    """
    
    def learn(self, prompt: str) -> Optional[re.Pattern]:
        """
        学习提示符模式
        
        将提示符转义为正则表达式，并将空格替换为可匹配任意空白的模式
        """
        if not prompt:
            return None
        
        try:
            # 转义特殊字符，但将转义后的空格替换为灵活匹配
            escaped = re.escape(prompt)
            # 将 \ 转义的空格替换为匹配任意空白
            pattern_str = escaped.replace(r'\ ', r'\s+') + r'\s*$'
            return re.compile(pattern_str)
        except re.error:
            logger.warning(f"无法学习提示符模式: {prompt}")
            return None


class PromptMatchResult:
    """
    提示符匹配结果
    
    包含匹配的详细信息和元数据
    """
    
    def __init__(
        self,
        is_match: bool,
        matched_text: Optional[str] = None,
        pattern_name: Optional[str] = None,
        category: Optional[PromptCategory] = None,
        is_learned: bool = False
    ):
        self.is_match = is_match
        self.matched_text = matched_text
        self.pattern_name = pattern_name
        self.category = category
        self.is_learned = is_learned
    
    def __bool__(self) -> bool:
        return self.is_match
    
    def __repr__(self) -> str:
        return f"PromptMatchResult(match={self.is_match}, text='{self.matched_text}')"


class PromptDetector:
    """
    提示符检测器（重构版）
    
    支持多种Shell类型的提示符检测，提供学习能力和输出清理功能。
    
    支持动态提示符场景（如 scapy、jupyter、ipython 等）：
    - 多模式学习：同时学习多个提示符模式
    - 上下文检测：自动检测提示符变化
    - 状态管理：支持进入/退出交互式程序时重置状态
    
    Example:
        # 基本使用
        detector = PromptDetector()
        result = detector.detect("user@host:~$")
        
        # 检查是否为提示符
        if detector.is_prompt_line("user@host:~$"):
            print("这是一个提示符")
        
        # 清理命令输出
        clean_output = detector.clean_output(raw_output, "ls -la")
        
        # 多模式学习场景（scapy/ipython）
        detector.learn_prompt(">>>")  # 学习 Python 提示符
        detector.learn_prompt("In [1]:")  # 学习 IPython 提示符
        
        # 进入交互式程序前保存状态
        context = detector.save_context()
        # ... 执行交互式命令 ...
        # 退出后恢复状态
        detector.restore_context(context)
    """
    
    DEFAULT_PROMPT = "#"
    MAX_LEARNED_PATTERNS = 10  # 最多学习的模式数量
    
    def __init__(
        self,
        patterns: Optional[List[PromptPattern]] = None,
        learning_strategy: Optional[PromptLearningStrategy] = None,
        enable_learning: bool = True,
        max_learned_patterns: Optional[int] = None
    ):
        """
        初始化提示符检测器
        
        Args:
            patterns: 自定义提示符模式列表，默认使用内置模式
            learning_strategy: 学习策略，默认使用DefaultLearningStrategy
            enable_learning: 是否启用学习功能
            max_learned_patterns: 最多学习的模式数量，默认10个
        """
        self._patterns = patterns or PromptPatternBuilder.build_all()
        self._learning_strategy = learning_strategy or DefaultLearningStrategy()
        self._enable_learning = enable_learning
        self._max_learned_patterns = max_learned_patterns or self.MAX_LEARNED_PATTERNS
        
        # 支持多模式学习
        self._learned_patterns: List[re.Pattern] = []
        self._learned_prompts: List[str] = []  # 记录学习的提示符文本
        self._last_prompt: Optional[str] = None
        self._match_history: List[PromptMatchResult] = []
        
        # 上下文管理
        self._context_stack: List[dict] = []  # 上下文栈，用于保存/恢复状态
    
    @property
    def last_prompt(self) -> Optional[str]:
        """获取最后检测到的提示符"""
        return self._last_prompt
    
    @property
    def learned_pattern(self) -> Optional[re.Pattern]:
        """获取最后学习的提示符模式（向后兼容）"""
        return self._learned_patterns[-1] if self._learned_patterns else None
    
    @property
    def learned_patterns(self) -> List[re.Pattern]:
        """获取所有学习的提示符模式"""
        return self._learned_patterns.copy()
    
    @property
    def learned_prompts(self) -> List[str]:
        """获取所有学习的提示符文本"""
        return self._learned_prompts.copy()
    
    @property
    def match_history(self) -> List[PromptMatchResult]:
        """获取匹配历史记录"""
        return self._match_history.copy()
    
    def reset(self) -> None:
        """重置检测器状态（清除学习和历史记录）"""
        self._learned_patterns.clear()
        self._learned_prompts.clear()
        self._last_prompt = None
        self._match_history.clear()
        self._context_stack.clear()
        logger.debug("PromptDetector状态已重置（包括所有学习模式）")
    
    def reset_learned_only(self) -> None:
        """只重置学习的状态，保留内置模式"""
        self._learned_patterns.clear()
        self._learned_prompts.clear()
        logger.debug("PromptDetector学习状态已重置")
    
    def save_context(self) -> dict:
        """
        保存当前上下文状态
        
        用于进入交互式程序前保存当前状态
        
        Returns:
            dict: 包含当前状态的上下文
        """
        context = {
            "learned_patterns": self._learned_patterns.copy(),
            "learned_prompts": self._learned_prompts.copy(),
            "last_prompt": self._last_prompt,
            "timestamp": time.time()
        }
        self._context_stack.append(context)
        logger.debug(f"保存上下文状态，栈深度: {len(self._context_stack)}")
        return context
    
    def restore_context(self, context: Optional[dict] = None) -> None:
        """
        恢复之前保存的上下文状态
        
        用于退出交互式程序后恢复之前的状态
        
        Args:
            context: 要恢复的上下文，为None时恢复最近一次保存的上下文
        """
        if context is None:
            if not self._context_stack:
                logger.warning("没有可恢复的上下文")
                return
            context = self._context_stack.pop()
        
        self._learned_patterns = context.get("learned_patterns", []).copy()
        self._learned_prompts = context.get("learned_prompts", []).copy()
        self._last_prompt = context.get("last_prompt")
        
        logger.debug(f"恢复上下文状态，提示符: {self._last_prompt}")
    
    def learn_prompt(self, prompt: str) -> bool:
        """
        显式学习一个提示符模式
        
        用于在进入交互式程序前手动学习特殊提示符
        
        Args:
            prompt: 要学习的提示符文本
            
        Returns:
            bool: 是否成功学习
        """
        if not prompt or not self._enable_learning:
            return False
        
        # 检查是否已经学习过相同的提示符
        if prompt in self._learned_prompts:
            logger.debug(f"提示符已存在: {prompt}")
            return True
        
        learned = self._learning_strategy.learn(prompt)
        if learned:
            # 如果超过最大数量，移除最早学习的
            if len(self._learned_patterns) >= self._max_learned_patterns:
                removed = self._learned_prompts.pop(0)
                self._learned_patterns.pop(0)
                logger.debug(f"学习模式数量超限，移除最早学习的: {removed}")
            
            self._learned_patterns.append(learned)
            self._learned_prompts.append(prompt)
            self._last_prompt = prompt
            logger.info(f"显式学习新提示符模式: {prompt}")
            return True
        
        return False
    
    def has_learned_prompt(self, prompt: str) -> bool:
        """
        检查是否已经学习了某个提示符
        
        Args:
            prompt: 要检查的提示符
            
        Returns:
            bool: 是否已学习
        """
        return prompt in self._learned_prompts
    
    def detect_prompt_change(self, old_prompt: str, new_output: str) -> Optional[str]:
        """
        检测提示符是否发生变化
        
        用于检测进入/退出交互式程序时的提示符变化
        
        Args:
            old_prompt: 之前的提示符
            new_output: 新的输出
            
        Returns:
            Optional[str]: 新检测到的提示符，如果未变化则返回None
        """
        detected = self.detect(new_output, learn=False)
        
        if detected != old_prompt:
            logger.info(f"检测到提示符变化: '{old_prompt}' -> '{detected}'")
            return detected
        
        return None
    
    def is_prompt_line(self, line: str) -> bool:
        """
        检查一行文本是否为提示符
        
        Args:
            line: 要检查的文本行
            
        Returns:
            bool: 是否为提示符
        """
        result = self.match_line(line)
        return result.is_match
    
    def match_line(self, line: str) -> PromptMatchResult:
        """
        匹配单行文本，返回详细结果
        
        支持多模式学习，会检查所有已学习的模式
        
        Args:
            line: 要匹配的文本行
            
        Returns:
            PromptMatchResult: 匹配结果
        """
        line = line.strip()
        if not line:
            return PromptMatchResult(is_match=False)
        
        # 首先检查已学习的模式（按最近学习的优先）
        for i, learned_pattern in enumerate(reversed(self._learned_patterns)):
            if learned_pattern.search(line):
                # 计算实际索引（因为使用了 reversed）
                actual_index = len(self._learned_patterns) - 1 - i
                learned_prompt = self._learned_prompts[actual_index] if actual_index < len(self._learned_prompts) else ""
                result = PromptMatchResult(
                    is_match=True,
                    matched_text=line,
                    is_learned=True
                )
                self._match_history.append(result)
                logger.debug(f"使用学习的模式匹配到提示符: {line} (学习的提示符: {learned_prompt})")
                return result
        
        # 使用标准模式库匹配
        for pattern in self._patterns:
            if pattern.pattern.match(line):
                result = PromptMatchResult(
                    is_match=True,
                    matched_text=line,
                    pattern_name=pattern.name,
                    category=pattern.category
                )
                self._match_history.append(result)
                return result
        
        return PromptMatchResult(is_match=False)
    
    def detect(self, output: str, learn: bool = True) -> str:
        """
        从shell输出中检测提示符
        
        从输出文本的最后一行开始向上搜索，找到匹配的提示符。
        
        Args:
            output: shell输出
            learn: 是否学习检测到的提示符模式
            
        Returns:
            str: 检测到的提示符
        """
        # 清理ANSI控制字符
        clean_output = ANSICleaner.clean(output)
        lines = clean_output.strip().split('\n')
        
        # 从后往前查找（提示符通常在最后）
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            
            match_result = self.match_line(line)
            if match_result.is_match:
                logger.debug(
                    f"检测到提示符: {line} "
                    f"(模式: {match_result.pattern_name or 'learned'}, "
                    f"类别: {match_result.category.name if match_result.category else 'unknown'})"
                )
                
                if learn and self._enable_learning:
                    self._learn_prompt(line)
                
                self._last_prompt = line
                return line
        
        # 如果没检测到，使用最后一行作为备选
        if lines:
            last_line = ANSICleaner.clean(lines[-1]).strip()
            if last_line:
                logger.debug(f"未匹配到已知模式，使用最后一行作为提示符: {last_line}")
                if learn and self._enable_learning:
                    self._learn_prompt(last_line)
                self._last_prompt = last_line
                return last_line
        
        # 默认prompt
        logger.debug("使用默认提示符")
        self._last_prompt = self.DEFAULT_PROMPT
        return self.DEFAULT_PROMPT
    
    def _learn_prompt(self, prompt: str) -> None:
        """
        学习提示符模式
        
        支持多模式学习，会检查是否已学习过相同模式
        
        Args:
            prompt: 要学习的提示符
        """
        if not prompt:
            return
        
        # 检查是否已经学习过相同的提示符
        if prompt in self._learned_prompts:
            # 更新为最近使用（移动到末尾）
            idx = self._learned_prompts.index(prompt)
            self._learned_prompts.pop(idx)
            self._learned_patterns.pop(idx)
            # 将提示符和模式添加到末尾（最近使用）
            learned = self._learning_strategy.learn(prompt)
            if learned:
                self._learned_patterns.append(learned)
                self._learned_prompts.append(prompt)
            logger.debug(f"更新提示符位置: {prompt} (当前共 {len(self._learned_patterns)} 个)")
            return
        
        learned = self._learning_strategy.learn(prompt)
        if learned:
            # 如果超过最大数量，移除最早学习的
            if len(self._learned_patterns) >= self._max_learned_patterns:
                removed_prompt = self._learned_prompts.pop(0)
                self._learned_patterns.pop(0)
                logger.debug(f"学习模式数量超限，移除最早学习的: {removed_prompt}")
            
            self._learned_patterns.append(learned)
            self._learned_prompts.append(prompt)
            logger.debug(f"学习了新的提示符模式: {prompt} (当前共 {len(self._learned_patterns)} 个)")
    
    def clean_output(self, output: str, command: str) -> str:
        """
        清理shell输出，移除命令本身和最后的提示符
        
        Args:
            output: 原始输出
            command: 执行的命令
            
        Returns:
            str: 清理后的输出
        """
        if not output:
            return ""
        
        # 首先清理所有ANSI控制字符
        clean_output = ANSICleaner.clean(output)
        lines = clean_output.split('\n')
        
        # 移除空行（开头和结尾）
        lines = self._strip_empty_lines(lines)
        
        if not lines:
            return ""
        
        # 移除命令回显（第一行）
        lines = self._strip_command_echo(lines, command)
        
        # 移除提示符（最后一行）
        lines = self._strip_prompt_line(lines)
        
        # 重新组合并清理
        result = '\n'.join(lines).strip()
        return result
    
    def _strip_empty_lines(self, lines: List[str]) -> List[str]:
        """移除开头和结尾的空行"""
        # 使用列表推导式更高效
        start = 0
        for i, line in enumerate(lines):
            if line.strip():
                start = i
                break
        
        end = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                end = i + 1
                break
        
        return lines[start:end]
    
    def _strip_command_echo(self, lines: List[str], command: str) -> List[str]:
        """移除命令回显"""
        if not lines:
            return lines
        
        first_line = lines[0]
        if command.strip() in first_line or first_line.strip().endswith(command.strip()):
            return lines[1:]
        
        return lines
    
    def _strip_prompt_line(self, lines: List[str]) -> List[str]:
        """移除提示符行"""
        if not lines:
            return lines
        
        last_line = lines[-1].strip()
        
        # 多种匹配策略
        if self._last_prompt:
            if (last_line == self._last_prompt or
                last_line.startswith(self._last_prompt) or
                self._last_prompt in last_line):
                return lines[:-1]
        
        # 使用匹配器检查最后一行是否为提示符
        if self.is_prompt_line(last_line):
            return lines[:-1]
        
        return lines
    
    def get_statistics(self) -> dict:
        """
        获取检测器统计信息
        
        Returns:
            dict: 包含统计信息的字典
        """
        categories = {}
        learned_count = 0
        
        for result in self._match_history:
            if result.is_learned:
                learned_count += 1
            elif result.category:
                cat_name = result.category.name
                categories[cat_name] = categories.get(cat_name, 0) + 1
        
        return {
            "total_matches": len(self._match_history),
            "learned_matches": learned_count,
            "category_distribution": categories,
            "has_learned_pattern": len(self._learned_patterns) > 0,
            "learned_patterns_count": len(self._learned_patterns),
            "last_prompt": self._last_prompt
        }
