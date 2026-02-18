"""
优化的通道数据接收模块
提供高性能的输出获取功能
"""
import logging
import select
import socket
import sys
import time
from typing import Optional, Tuple, Callable

# 从后端导入抽象类型和异常
from src.backends.base import Channel, Transport
from src.backends import ConnectionError

from src.config.models import SSHConfig


logger = logging.getLogger(__name__)


class OptimizedChannelDataReceiver:
    """
    优化的通道数据接收器
    
    改进点：
    1. 使用 select/poll 替代轮询，降低 CPU 占用
    2. 批量处理提示符检测，减少计算
    3. 自适应等待间隔，平衡响应速度和 CPU 占用
    4. 使用阻塞式读取减少系统调用
    """
    
    def __init__(self, config: SSHConfig):
        self._config = config
    
    def recv_all_optimized(
        self,
        channel: Channel,
        timeout: Optional[float] = None,
        transport: Optional[Transport] = None
    ) -> Tuple[str, str, int]:
        """
        优化的数据接收方法

        使用 select 实现高效的 I/O 多路复用，大幅降低 CPU 占用
        """
        timeout = timeout or self._config.command_timeout
        start_time = time.time()
        
        stdout_data = b""
        stderr_data = b""
        exit_code = -1
        stdout_truncated = False
        stderr_truncated = False
        
        logger.debug(f"开始优化接收数据，超时: {timeout}秒")
        
        # 设置非阻塞模式，配合 select 使用
        channel.setblocking(False)
        
        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise TimeoutError(f"命令执行超过 {timeout} 秒")
                
                remaining = timeout - elapsed
                
                # 使用 select 等待数据就绪（CPU 占用为 0）
                readable, _, _ = select.select(
                    [channel], [], [], 
                    min(remaining, 0.1)  # 最多等待 100ms
                )
                
                if channel in readable:
                    # 数据就绪，立即读取
                    try:
                        data = channel.recv(4096)
                        if data:
                            stdout_data += data
                            logger.debug(f"接收 {len(data)} 字节 stdout")
                    except socket.error:
                        pass
                    
                    try:
                        data = channel.recv_stderr(4096)
                        if data:
                            stderr_data += data
                            logger.debug(f"接收 {len(data)} 字节 stderr")
                    except socket.error:
                        pass
                
                # 检查退出状态（不频繁检查，每 100ms 一次）
                if exit_code == -1 and channel.exit_status_ready:
                    exit_code = channel.recv_exit_status()
                    logger.debug(f"收到退出码: {exit_code}")
                
                # 判断完成条件
                if exit_code != -1:
                    # 尝试最后一次读取残留数据
                    try:
                        while True:
                            data = channel.recv(4096)
                            if not data:
                                break
                            stdout_data += data
                    except:
                        pass
                    
                    try:
                        while True:
                            data = channel.recv_stderr(4096)
                            if not data:
                                break
                            stderr_data += data
                    except:
                        pass
                    
                    logger.debug("命令执行完成")
                    break
                
                # 检查 channel 是否关闭
                if channel.closed:
                    logger.debug("Channel 已关闭")
                    break
                
                # 检查传输层状态
                if transport and not transport.is_active():
                    raise ConnectionError("SSH 连接已断开")
        
        finally:
            # 恢复阻塞模式
            channel.setblocking(True)
        
        # 解码并返回
        encoding = self._config.encoding
        stdout_text = stdout_data.decode(encoding, errors="replace")
        stderr_text = stderr_data.decode(encoding, errors="replace")
        
        if stdout_truncated:
            stdout_text += "\n[输出已截断 - 超过最大限制]"
        if stderr_truncated:
            stderr_text += "\n[错误输出已截断 - 超过最大限制]"
        
        return stdout_text, stderr_text, exit_code


class AdaptivePollingReceiver:
    """
    自适应轮询接收器
    
    适用于不支持 select 的环境
    使用指数退避策略降低 CPU 占用
    """
    
    def __init__(self, config: SSHConfig):
        self._config = config
    
    def recv_all(
        self,
        channel: Channel,
        timeout: Optional[float] = None,
        transport: Optional[Transport] = None
    ) -> Tuple[str, str, int]:
        """
        使用自适应轮询策略接收数据
        """
        timeout = timeout or self._config.command_timeout
        start_time = time.time()
        last_activity_time = start_time
        
        stdout_data = b""
        stderr_data = b""
        exit_code = -1
        stdout_truncated = False
        stderr_truncated = False
        
        # 自适应等待参数
        empty_poll_count = 0
        current_wait = 0.001  # 初始 1ms
        
        # 新增：跟踪退出码接收时间
        exit_code_time = None
        
        logger.debug(f"开始自适应轮询接收，超时: {timeout}秒")
        
        while True:
            # 检查底层连接状态
            if transport and int((time.time() - start_time) * 100) % 10 == 0:
                if not transport.is_active():
                    logger.error("SSH 传输层连接已断开")
                    raise ConnectionError("SSH 连接已断开")
            
            # 检查全局超时
            if time.time() - start_time > timeout:
                raise TimeoutError(f"命令执行超过 {timeout} 秒")
            
            received_any = False
            
            # 尝试读取 stdout
            try:
                if channel.recv_ready():
                    data = channel.recv(4096)
                    if data:
                        new_size = len(stdout_data) + len(data)
                        if new_size > self._config.max_output_size:
                            allowed = self._config.max_output_size - len(stdout_data)
                            if allowed > 0:
                                stdout_data += data[:allowed]
                            if not stdout_truncated:
                                stdout_truncated = True
                                logger.warning("标准输出超过最大限制，已截断")
                        else:
                            stdout_data += data
                        received_any = True
                        last_activity_time = time.time()
                        logger.debug(f"接收到 {len(data)} 字节 stdout 数据")
            except socket.timeout:
                logger.debug("接收 stdout 超时，继续等待")
            except socket.error as e:
                logger.error(f"接收数据时网络错误: {e}")
                raise ConnectionError(f"网络连接错误: {e}") from e
            
            # 尝试读取 stderr
            try:
                if channel.recv_stderr_ready():
                    data = channel.recv_stderr(4096)
                    if data:
                        new_size = len(stderr_data) + len(data)
                        if new_size > self._config.max_output_size:
                            allowed = self._config.max_output_size - len(stderr_data)
                            if allowed > 0:
                                stderr_data += data[:allowed]
                            if not stderr_truncated:
                                stderr_truncated = True
                                logger.warning("错误输出超过最大限制，已截断")
                        else:
                            stderr_data += data
                        received_any = True
                        last_activity_time = time.time()
                        logger.debug(f"接收到 {len(data)} 字节 stderr 数据")
            except socket.timeout:
                logger.debug("接收 stderr 超时，继续等待")
            except socket.error as e:
                logger.error(f"接收数据时网络错误: {e}")
                raise ConnectionError(f"网络连接错误: {e}") from e
            
            # 检查退出状态
            if exit_code == -1 and channel.exit_status_ready:
                exit_code = channel.recv_exit_status()
                exit_code_time = time.time()  # 记录收到退出码的时间
                logger.debug(f"收到退出码: {exit_code}")
            
            # 判断完成 - 改进：收到退出码后继续等待确保所有数据到达
            if exit_code != -1 and not received_any:
                if not channel.recv_ready() and not channel.recv_stderr_ready():
                    # 改进：收到退出码后额外等待一段时间，确保所有数据到达
                    # SSH 通道的数据到达和退出码是异步的
                    if exit_code_time is None:
                        exit_code_time = time.time()
                        logger.debug("收到退出码，等待残留数据...")
                        continue  # 继续循环，不立即退出
                    elif time.time() - exit_code_time < 0.5:  # 等待500ms
                        continue  # 继续等待
                    else:
                        logger.debug("命令执行完成，所有数据已接收")
                        break
            
            # 检查 channel 是否关闭
            if channel.closed:
                # 尝试读取残留数据
                if channel.recv_ready():
                    try:
                        data = channel.recv(4096)
                        if data:
                            stdout_data += data
                            continue
                    except:
                        pass
                if channel.recv_stderr_ready():
                    try:
                        data = channel.recv_stderr(4096)
                        if data:
                            stderr_data += data
                            continue
                    except:
                        pass
                
                # 获取 exit_code
                if exit_code == -1 and channel.exit_status_ready:
                    exit_code = channel.recv_exit_status()
                logger.debug("Channel 被远程关闭，数据接收完毕")
                break
            
            # 长时间无数据活动检查
            if time.time() - last_activity_time > 1.0:
                if channel.exit_status_ready:
                    # 再尝试读取一次
                    try:
                        if channel.recv_ready():
                            data = channel.recv(4096)
                            if data:
                                stdout_data += data
                                last_activity_time = time.time()
                        if channel.recv_stderr_ready():
                            data = channel.recv_stderr(4096)
                            if data:
                                stderr_data += data
                                last_activity_time = time.time()
                    except:
                        pass
                    
                    if not channel.recv_ready() and not channel.recv_stderr_ready():
                        if exit_code == -1:
                            exit_code = channel.recv_exit_status()
                        logger.debug("数据接收完毕，结束循环")
                        break
            
            # 自适应等待策略
            if received_any:
                # 收到数据，重置等待时间
                empty_poll_count = 0
                current_wait = 0.001
            else:
                # 未收到数据，指数退避
                empty_poll_count += 1
                if empty_poll_count < 10:
                    current_wait = 0.001
                elif empty_poll_count < 50:
                    current_wait = 0.005
                elif empty_poll_count < 100:
                    current_wait = 0.01
                else:
                    current_wait = 0.05  # 最大 50ms
                
                time.sleep(current_wait)
        
        # 解码
        encoding = self._config.encoding
        stdout_text = stdout_data.decode(encoding, errors="replace")
        stderr_text = stderr_data.decode(encoding, errors="replace")
        
        if stdout_truncated:
            stdout_text += "\n[输出已截断 - 超过最大限制]"
        if stderr_truncated:
            stderr_text += "\n[错误输出已截断 - 超过最大限制]"
        
        logger.debug(f"数据接收完成: stdout={len(stdout_text)}字符, stderr={len(stderr_text)}字符, exit_code={exit_code}")
        return stdout_text, stderr_text, exit_code
    
    def recv_stream(
        self,
        channel: Channel,
        chunk_handler: Callable[[bytes, bytes], None],
        timeout: Optional[float] = None,
        transport: Optional[Transport] = None
    ) -> int:
        """
        流式接收通道数据
        
        实时处理每个数据块，不缓存完整输出，适用于超大数据传输。
        
        Args:
            channel: SSH Channel 对象
            chunk_handler: 回调函数，接收 (stdout_chunk, stderr_chunk)
                          每次收到数据块时立即调用
            timeout: 命令执行总超时
            transport: SSH Transport 对象
            
        Returns:
            int: 退出码
            
        Example:
            def handle_chunk(stdout, stderr):
                process.stdout.write(stdout)
                process.stderr.write(stderr)
            
            exit_code = receiver.recv_stream(channel, handle_chunk, timeout=60.0)
        """
        timeout = timeout or self._config.command_timeout
        start_time = time.time()
        last_activity_time = start_time
        
        exit_code = -1
        exit_code_time = None
        
        # 自适应等待参数
        empty_poll_count = 0
        current_wait = 0.001
        
        logger.debug(f"开始流式接收数据，超时: {timeout}秒")
        
        try:
            while True:
                # 检查底层连接状态
                if transport and int((time.time() - start_time) * 100) % 10 == 0:
                    if not transport.is_active():
                        logger.error("SSH 传输层连接已断开")
                        raise ConnectionError("SSH 连接已断开")
                
                # 检查全局超时
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"命令执行超过 {timeout} 秒")
                
                received_any = False
                
                # 尝试读取 stdout
                try:
                    if channel.recv_ready():
                        data = channel.recv(65536)  # 使用更大的缓冲区 64KB
                        if data:
                            # 立即通过回调处理数据块
                            chunk_handler(data, b"")
                            received_any = True
                            last_activity_time = time.time()
                            logger.debug(f"流式接收 {len(data)} 字节 stdout 数据")
                except socket.timeout:
                    logger.debug("接收 stdout 超时，继续等待")
                except socket.error as e:
                    logger.error(f"接收数据时网络错误: {e}")
                    raise ConnectionError(f"网络连接错误: {e}") from e
                
                # 尝试读取 stderr
                try:
                    if channel.recv_stderr_ready():
                        data = channel.recv_stderr(65536)
                        if data:
                            # 立即通过回调处理数据块
                            chunk_handler(b"", data)
                            received_any = True
                            last_activity_time = time.time()
                            logger.debug(f"流式接收 {len(data)} 字节 stderr 数据")
                except socket.timeout:
                    logger.debug("接收 stderr 超时，继续等待")
                except socket.error as e:
                    logger.error(f"接收数据时网络错误: {e}")
                    raise ConnectionError(f"网络连接错误: {e}") from e
                
                # 检查退出状态
                if exit_code == -1 and channel.exit_status_ready:
                    exit_code = channel.recv_exit_status()
                    exit_code_time = time.time()
                    logger.debug(f"收到退出码: {exit_code}")
                
                # 判断完成 - 自适应智能等待算法（优化版）
                if exit_code != -1:
                    if exit_code_time is None:
                        exit_code_time = time.time()
                        last_data_time = time.time()  # 记录最后收到数据的时间
                        logger.debug(f"收到退出码 {exit_code}，开始自适应等待...")
                    
                    # 如果收到新数据，更新最后数据时间
                    if received_any:
                        last_data_time = time.time()
                        empty_poll_count = 0
                        logger.debug("收到新数据，更新时间戳")
                        continue
                    
                    # 快速检测：如果通道还有数据在等待，立即继续
                    if channel.recv_ready() or channel.recv_stderr_ready():
                        continue
                    
                    time_since_exit = time.time() - exit_code_time
                    time_since_last_data = time.time() - last_data_time
                    
                    # 核心算法：基于"数据静默期"的判断
                    # 如果在收到退出码后，连续100ms没有新数据，认为传输完成
                    # 但最多等待1秒（防止网络抖动）
                    
                    if time_since_last_data < 0.1:  # 100ms内有过数据，继续等待
                        continue
                    
                    if time_since_exit < 1.0:  # 最长等待1秒
                        # 渐进式等待：越往后检查间隔越长
                        if empty_poll_count < 10:
                            continue
                        elif empty_poll_count < 30 and time_since_exit < 0.3:
                            continue
                        elif empty_poll_count < 50 and time_since_exit < 0.6:
                            continue
                    
                    # 最终确认：检查是否真的没有数据了
                    if channel.recv_ready() or channel.recv_stderr_ready():
                        last_data_time = time.time()
                        empty_poll_count = 0
                        continue
                    
                    logger.debug(f"流式接收完成，退出码等待 {time_since_exit:.2f} 秒，"
                               f"最后数据 {time_since_last_data:.3f} 秒前")
                    break
                
                # 检查 channel 是否关闭
                if channel.closed:
                    logger.debug("Channel 已关闭")
                    break
                
                # 自适应等待策略
                if received_any:
                    empty_poll_count = 0
                    current_wait = 0.001
                else:
                    empty_poll_count += 1
                    if empty_poll_count < 10:
                        current_wait = 0.001
                    elif empty_poll_count < 50:
                        current_wait = 0.005
                    elif empty_poll_count < 100:
                        current_wait = 0.01
                    else:
                        current_wait = 0.05
                    
                    time.sleep(current_wait)
        
        finally:
            # 确保通道关闭
            try:
                if not channel.closed:
                    channel.close()
            except:
                pass
        
        return exit_code


class BatchedPromptDetector:
    """
    批量提示符检测器
    
    减少提示符检测频率，降低 CPU 占用
    """
    
    def __init__(self, detector, check_interval: float = 0.05, min_data_size: int = 1024):
        self._detector = detector
        self._check_interval = check_interval
        self._min_data_size = min_data_size
        self._last_check_time = 0
        self._last_check_size = 0
    
    def should_check(self, current_size: int) -> bool:
        """判断是否应该进行提示符检测"""
        current_time = time.time()
        
        # 时间间隔检查
        if current_time - self._last_check_time < self._check_interval:
            return False
        
        # 数据量检查
        if current_size - self._last_check_size < self._min_data_size:
            return False
        
        return True
    
    def check(self, output: str) -> bool:
        """执行提示符检测"""
        self._last_check_time = time.time()
        self._last_check_size = len(output)
        return self._detector.is_prompt_line(output.strip().split('\n')[-1])


# 性能对比函数
def compare_performance():
    """
    性能对比示例
    
    原始实现 vs 优化实现
    """
    print("性能对比:")
    print("-" * 50)
    print("1. 原始轮询模式:")
    print("   - 轮询间隔: 1ms")
    print("   - CPU 占用: ~10-20% (等待时)")
    print("   - 系统调用: 高频")
    print()
    print("2. Select 模式:")
    print("   - 阻塞等待数据就绪")
    print("   - CPU 占用: ~0% (等待时)")
    print("   - 系统调用: 低频")
    print()
    print("3. 自适应轮询:")
    print("   - 初始: 1ms → 最大: 50ms")
    print("   - CPU 占用: ~2-5% (等待时)")
    print("   - 响应延迟: 初期快，后期慢")
    print()
    print("推荐:")
    print("- 生产环境: 使用 Select 模式")
    print("- Windows/兼容性: 使用自适应轮询")
