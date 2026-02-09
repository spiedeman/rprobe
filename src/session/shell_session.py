"""
Shell 会话管理模块
提供持久 Shell 会话的管理和命令执行
"""
import logging
import socket
import time
from typing import Optional

import paramiko

from src.config.models import SSHConfig
from src.patterns.prompt_detector import PromptDetector
from src.utils.ansi_cleaner import ANSICleaner
from src.utils.wait_strategies import AdaptiveWaitStrategy


logger = logging.getLogger(__name__)


class ShellSession:
    """
    Shell 会话
    
    管理一个持久的 Shell 会话，支持状态保持和提示符检测。
    
    支持动态提示符场景（如 scapy、jupyter、ipython 等）：
    - 进入交互式程序前保存当前上下文
    - 自动学习新的提示符模式
    - 退出交互式程序后恢复之前的上下文
    
    Example:
        session = ShellSession(channel, config)
        session.initialize()
        
        # 执行普通命令
        output = session.execute_command("ls -la")
        
        # 进入交互式程序（如 scapy）
        session.enter_interactive("scapy")
        output = session.execute_interactive("ls()")  # 在 scapy 中执行
        session.exit_interactive()  # 退出 scapy
        
        # 继续执行普通命令
        output = session.execute_command("pwd")
    """
    
    # 常见的交互式程序及其提示符特征
    INTERACTIVE_PROGRAMS = {
        'python': ['>>>', '...'],
        'ipython': ['In [', r'In \d+:', r'Out\[\d+\]:'],
        'scapy': ['>>>', '...'],
        'jupyter': ['In [', r'In \d+:'],
        'bc': [''],
        'gdb': ['(gdb)'],
        'redis-cli': ['redis', '127.0.0.1:', '>'],
        'psql': ['=', '#', '=>', '->', '~#'],
        'mysql': ['mysql>', '->'],
    }
    
    def __init__(
        self,
        channel: paramiko.Channel,
        config: SSHConfig,
        prompt_detector: Optional[PromptDetector] = None
    ):
        """
        初始化 Shell 会话
        
        Args:
            channel: SSH 通道
            config: SSH 配置
            prompt_detector: 提示符检测器，默认创建新的
        """
        self._channel = channel
        self._config = config
        self._prompt_detector = prompt_detector or PromptDetector()
        self._is_open = True
        self._in_interactive = False
        self._interactive_program = None
        self._saved_context = None
        
    @property
    def is_active(self) -> bool:
        """检查会话是否活跃"""
        return self._is_open and not self._channel.closed
    
    @property
    def prompt(self) -> Optional[str]:
        """获取当前提示符"""
        return self._prompt_detector.last_prompt
    
    def initialize(self, timeout: Optional[float] = None) -> str:
        """
        初始化会话并检测提示符
        
        Args:
            timeout: 超时时间
            
        Returns:
            str: 检测到的提示符
        """
        timeout = timeout or self._config.command_timeout
        logger.info("正在打开 Shell 会话...")
        
        self._channel.get_pty()
        self._channel.invoke_shell()
        self._channel.settimeout(timeout)
        
        # 等待 shell 初始输出
        logger.debug("等待 shell 初始输出...")
        start_time = time.time()
        initial_output = ""
        
        # 使用自适应等待策略，平衡响应速度和CPU占用
        # 开始时间隔短（快速响应），逐渐增长（减少CPU占用）
        waiter = AdaptiveWaitStrategy(
            initial_wait=0.001,    # 1ms - 快速启动
            max_wait=0.02,         # 20ms - 最大等待
            growth_factor=1.3      # 30%增长
        )
        
        while time.time() - start_time < timeout:
            if self._channel.recv_ready():
                data = self._channel.recv(4096).decode(
                    self._config.encoding, errors="replace"
                )
                initial_output += data
                logger.debug(f"收到初始输出: {len(data)} 字节")
                
                # 检查是否包含 prompt 模式
                clean_output = ANSICleaner.clean(initial_output)
                lines = clean_output.strip().split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    if self._prompt_detector.is_prompt_line(last_line):
                        logger.debug(f"检测到 prompt 模式: {last_line}")
                        break
                
                # 收到数据后重置等待时间，保持响应性
                waiter.reset()
            else:
                # 没有数据时，使用自适应等待
                waiter.wait()
        
        # 检测 prompt
        prompt = self._prompt_detector.detect(initial_output, learn=True)
        logger.info(f"Shell 会话已打开，检测到提示符: {prompt}")
        return prompt
    
    def execute_command(self, command: str, timeout: Optional[float] = None) -> str:
        """
        在会话中执行命令
        
        Args:
            command: 要执行的命令
            timeout: 命令执行超时
            
        Returns:
            str: 命令输出
        """
        if not self.is_active:
            raise RuntimeError("Shell 会话未激活")
        
        cmd_timeout = timeout or self._config.command_timeout
        start_time = time.time()
        
        logger.info(f"[shell] 执行命令: {command}")
        
        # 发送命令
        self._channel.send(f"{command}\n".encode(self._config.encoding))
        
        # 等待输出和 prompt
        output = self._wait_for_output(timeout=cmd_timeout)
        
        execution_time = time.time() - start_time
        logger.info(f"[shell] 命令执行完成，耗时={execution_time:.3f}秒")
        
        # 清理输出
        clean_output = self._prompt_detector.clean_output(output, command)
        return clean_output
    
    def _wait_for_output(self, timeout: Optional[float] = None) -> str:
        """
        等待并读取输出直到检测到 prompt
        
        使用自适应等待策略，在响应速度和CPU占用之间取得平衡。
        
        Args:
            timeout: 超时时间
            
        Returns:
            str: 读取到的输出
        """
        timeout = timeout or self._config.command_timeout
        start_time = time.time()
        output_bytes = b""
        last_data_time = start_time
        
        logger.debug(f"开始等待提示符，超时: {timeout}秒")
        
        # 使用自适应等待策略
        waiter = AdaptiveWaitStrategy(
            initial_wait=0.001,    # 1ms - 快速启动
            max_wait=0.02,         # 20ms - 减少CPU占用
            growth_factor=1.3      # 30%增长
        )
        
        while True:
            # 读取 stdout 数据（shell 通道 stderr 混入 stdout）
            received_data = False
            try:
                if self._channel.recv_ready():
                    data = self._channel.recv(4096)
                    if data:
                        output_bytes += data
                        last_data_time = time.time()
                        received_data = True
                        logger.debug(f"Shell 接收到 {len(data)} 字节数据")
                        # 收到数据后重置等待策略，保持响应性
                        waiter.reset()
            except socket.timeout:
                logger.debug("Shell 接收数据超时，继续等待")
            
            # 检查是否检测到 prompt
            output = output_bytes.decode(self._config.encoding, errors="replace")
            clean_output = ANSICleaner.clean(output)
            lines = clean_output.strip().split('\n')
            
            if lines:
                last_line = lines[-1].strip()
                if self._prompt_detector.is_prompt_line(last_line):
                    # 检测到了 prompt
                    logger.debug(f"检测到提示符: {last_line}")
                    
                    # 等待一小段时间确保没有更多输出
                    time.sleep(0.01)  # 10ms 短等待
                    # 再次读取确保没有遗漏数据
                    try:
                        if self._channel.recv_ready():
                            data = self._channel.recv(4096)
                            if data:
                                output_bytes += data
                                waiter.reset()
                                continue  # 还有数据，继续循环
                    except Exception:
                        pass
                    
                    return output_bytes.decode(self._config.encoding, errors="replace")
            
            # 如果一段时间没有数据，且已经收到了一些输出，尝试最后确认
            if output_bytes and (time.time() - last_data_time) > 0.1:
                clean_output = ANSICleaner.clean(output_bytes.decode(self._config.encoding, errors="replace"))
                lines = clean_output.strip().split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    if self._prompt_detector.is_prompt_line(last_line):
                        logger.debug("数据接收完毕，检测到提示符 (静默检测)")
                        return output_bytes.decode(self._config.encoding, errors="replace")
            
            # 检查全局超时
            if time.time() - start_time > timeout:
                logger.error(f"等待 Shell 输出超时 ({timeout}秒)")
                if output_bytes:
                    logger.debug(f"已接收的输出: {repr(output_bytes[:200])}...")
                raise TimeoutError(f"等待输出超过 {timeout} 秒")
            
            # 没有数据时，使用自适应等待
            if not received_data:
                waiter.wait()

    def enter_interactive(
        self,
        program: str,
        prompt: Optional[str] = None,
        learn_prompts: Optional[list] = None
    ) -> str:
        """
        进入交互式程序前保存当前上下文

        用于进入 scapy、ipython、python 等交互式程序前保存当前 shell 状态。
        会自动学习交互式程序的提示符。

        Args:
            program: 交互式程序名称（如 'python', 'scapy', 'ipython'）
            prompt: 可选，指定新的主提示符。如果提供，将优先使用此提示符
            learn_prompts: 可选的提示符列表，用于学习特殊提示符（如次级提示符）

        Returns:
            str: 进入交互式程序后的初始输出

        Example:
            # 进入 scapy
            output = session.enter_interactive("scapy")

            # 指定新的主提示符
            session.enter_interactive("mytool", prompt="mytool>")

            # 指定主提示符和次级提示符
            session.enter_interactive("python", prompt=">>>", learn_prompts=["..."])

            # 仅学习额外提示符
            session.enter_interactive("mytool", learn_prompts=[">>>", "...>"])
        """
        if not self.is_active:
            raise RuntimeError("Shell 会话未激活")

        logger.info(f"准备进入交互式程序: {program}")

        # 保存当前上下文
        self._saved_context = self._prompt_detector.save_context()
        logger.debug(f"保存当前上下文，提示符: {self._prompt_detector.last_prompt}")

        # 清空当前学习状态，为新的交互式环境做准备
        self._prompt_detector.reset_learned_only()

        # 如果指定了主提示符，优先学习它
        if prompt:
            self._prompt_detector.learn_prompt(prompt)
            self._prompt_detector._last_prompt = prompt
            logger.info(f"使用指定的主提示符: {prompt}")

        # 预学习交互式程序的提示符
        known_prompts = self.INTERACTIVE_PROGRAMS.get(program.lower(), [])
        for p in known_prompts:
            # 如果已经指定了主提示符，跳过与之相同的预定义提示符
            if prompt and p == prompt:
                continue
            self._prompt_detector.learn_prompt(p)
            logger.debug(f"预学习提示符: {p}")

        # 学习用户自定义的提示符
        if learn_prompts:
            for p in learn_prompts:
                # 如果已经指定了主提示符，跳过与之相同的自定义提示符
                if prompt and p == prompt:
                    continue
                self._prompt_detector.learn_prompt(p)

        # 发送进入命令
        self._channel.send(f"{program}\n".encode(self._config.encoding))

        # 等待并返回初始输出
        output = self._wait_for_output(timeout=10)

        # 如果没有指定主提示符，尝试从输出中检测
        if not prompt:
            new_prompt = self._prompt_detector.detect(output, learn=True)
            logger.info(f"已进入交互式程序 {program}，检测到提示符: {new_prompt}")
        else:
            # 确保 last_prompt 是主提示符（防止被 learn_prompts 覆盖）
            self._prompt_detector._last_prompt = prompt
            logger.info(f"已进入交互式程序 {program}，使用指定提示符: {prompt}")

        self._in_interactive = True
        self._interactive_program = program

        return output

    def exit_interactive(self, exit_command: str = "exit()") -> str:
        """
        退出交互式程序并恢复之前的上下文
        
        发送退出命令，等待回到正常的 shell 提示符，并恢复之前保存的上下文。
        
        Args:
            exit_command: 退出命令，默认为 'exit()'
            
        Returns:
            str: 退出后的输出
            
        Example:
            # 退出 scapy 回到普通 shell
            output = session.exit_interactive()
            
            # 或者使用自定义退出命令
            session.exit_interactive("quit()")
        """
        if not self.is_active:
            raise RuntimeError("Shell 会话未激活")
        
        if not self._in_interactive:
            logger.warning("当前不在交互式程序中")
            return ""
        
        logger.info(f"退出交互式程序: {self._interactive_program}")
        
        # 发送退出命令
        self._channel.send(f"{exit_command}\n".encode(self._config.encoding))
        
        # 等待退出完成
        output = self._wait_for_output(timeout=10)
        
        # 恢复之前的上下文
        if self._saved_context:
            self._prompt_detector.restore_context(self._saved_context)
            logger.debug(f"恢复上下文，提示符: {self._prompt_detector.last_prompt}")
        
        self._in_interactive = False
        self._interactive_program = None
        self._saved_context = None
        
        logger.info("已退出交互式程序，恢复正常 shell")
        return output

    def execute_interactive(self, command: str, timeout: Optional[float] = None) -> str:
        """
        在交互式程序中执行命令
        
        用于在已进入的交互式程序（如 scapy、ipython）中执行命令。
        
        Args:
            command: 要执行的命令
            timeout: 命令执行超时
            
        Returns:
            str: 命令输出
            
        Example:
            session.enter_interactive("scapy")
            output = session.execute_interactive("ls()")  # 在 scapy 中执行 ls()
            session.exit_interactive()
        """
        if not self.is_active:
            raise RuntimeError("Shell 会话未激活")
        
        if not self._in_interactive:
            raise RuntimeError("当前不在交互式程序中，请先调用 enter_interactive()")
        
        cmd_timeout = timeout or self._config.command_timeout
        start_time = time.time()
        
        logger.info(f"[interactive] 执行命令: {command}")
        
        # 发送命令
        self._channel.send(f"{command}\n".encode(self._config.encoding))
        
        # 等待输出
        output = self._wait_for_output(timeout=cmd_timeout)
        
        execution_time = time.time() - start_time
        logger.info(f"[interactive] 命令执行完成，耗时={execution_time:.3f}秒")
        
        # 检测是否有新的提示符变化（学习新提示符）
        clean_output = ANSICleaner.clean(output)
        lines = clean_output.strip().split('\n')
        if lines:
            last_line = lines[-1].strip()
            if last_line and not self._prompt_detector.is_prompt_line(last_line):
                # 最后一行不是已知提示符，可能是新提示符
                self._prompt_detector.learn_prompt(last_line)
        
        return output

    @property
    def is_in_interactive(self) -> bool:
        """检查当前是否在交互式程序中"""
        return self._in_interactive

    @property
    def current_interactive_program(self) -> Optional[str]:
        """获取当前所在的交互式程序名称"""
        return self._interactive_program

    def close(self) -> None:
        """关闭 Shell 会话"""
        if not self._is_open:
            return
        
        try:
            self._channel.close()
            logger.info("Shell 会话已关闭")
        except Exception as e:
            logger.warning(f"关闭 Shell 会话时出错: {e}")
        finally:
            self._is_open = False
            self._prompt_detector.reset()
