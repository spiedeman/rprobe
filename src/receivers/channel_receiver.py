"""
SSH 通道数据接收模块
提供通道数据的接收和处理功能
"""
import logging
import socket
import time
from typing import Optional, Tuple

import paramiko

from src.config.models import SSHConfig


logger = logging.getLogger(__name__)


class ChannelDataReceiver:
    """
    通道数据接收器
    
    负责从 SSH 通道接收数据，提供超时控制、
    大小限制和网络健壮性检查。
    """
    
    def __init__(self, config: SSHConfig):
        """
        初始化数据接收器
        
        Args:
            config: SSH 配置
        """
        self._config = config
    
    def recv_once(
        self,
        channel: paramiko.Channel,
        is_stderr: bool = False,
        current_size: int = 0
    ) -> Tuple[bytes, bool]:
        """
        从通道读取单次数据
        
        Args:
            channel: paramiko Channel 对象
            is_stderr: 是否读取 stderr
            current_size: 已接收数据的当前大小
            
        Returns:
            Tuple[bytes, bool]: (读取到的数据, 是否达到大小限制)
        """
        max_limit = self._config.max_output_size
        
        try:
            # 检查数据是否就绪
            if is_stderr:
                ready = channel.recv_stderr_ready()
                recv_func = channel.recv_stderr
            else:
                ready = channel.recv_ready()
                recv_func = channel.recv
            
            if ready:
                data = recv_func(4096)
                if data:
                    new_size = current_size + len(data)
                    if new_size > max_limit:
                        # 返回截断的数据
                        allowed = max_limit - current_size
                        if allowed > 0:
                            return data[:allowed], True
                        return b"", True
                    return data, False
        except socket.timeout:
            raise
        except socket.error as e:
            logger.error(f"接收数据时网络错误: {e}")
            raise ConnectionError(f"网络连接错误: {e}") from e
        
        return b"", False
    
    def recv_all(
        self,
        channel: paramiko.Channel,
        timeout: Optional[float] = None,
        transport: Optional[paramiko.Transport] = None
    ) -> Tuple[str, str, int]:
        """
        智能接收通道所有数据直到完成
        
        Args:
            channel: paramiko Channel 对象
            timeout: 命令执行总超时
            transport: SSH Transport 对象，用于检查连接状态
            
        Returns:
            Tuple[str, str, int]: (stdout 文本, stderr 文本, exit_code)
        """
        timeout = timeout or self._config.command_timeout
        start_time = time.time()
        last_activity_time = start_time
        
        stdout_data = b""
        stderr_data = b""
        exit_code = -1
        stdout_truncated = False
        stderr_truncated = False
        
        logger.debug(f"开始接收 channel 数据，超时设置: {timeout}秒")
        
        while True:
            # 检查底层连接状态
            if transport and int((time.time() - start_time) * 100) % 10 == 0:
                if not transport.is_active():
                    logger.error("SSH 传输层连接已断开")
                    raise ConnectionError("SSH 连接已断开")
            
            # 读取 stdout 数据
            try:
                data, truncated = self.recv_once(channel, is_stderr=False, current_size=len(stdout_data))
                if data:
                    stdout_data += data
                    last_activity_time = time.time()
                    logger.debug(f"接收到 {len(data)} 字节 stdout 数据")
                if truncated and not stdout_truncated:
                    stdout_truncated = True
                    logger.warning("标准输出超过最大限制，已截断")
            except socket.timeout:
                logger.debug("接收 stdout 超时，继续等待")
            except ConnectionError:
                raise
            
            # 读取 stderr 数据
            try:
                data, truncated = self.recv_once(channel, is_stderr=True, current_size=len(stderr_data))
                if data:
                    stderr_data += data
                    last_activity_time = time.time()
                    logger.debug(f"接收到 {len(data)} 字节 stderr 数据")
                if truncated and not stderr_truncated:
                    stderr_truncated = True
                    logger.warning("错误输出超过最大限制，已截断")
            except socket.timeout:
                logger.debug("接收 stderr 超时，继续等待")
            except ConnectionError:
                raise
            
            # 检查退出状态
            if channel.exit_status_ready():
                exit_code = channel.recv_exit_status()
                logger.debug(f"收到退出码: {exit_code}")
            
            # 判断命令是否执行完成
            if exit_code != -1:
                if not channel.recv_ready() and not channel.recv_stderr_ready():
                    logger.debug("命令执行完成，所有数据已接收")
                    break
            
            # 检查 channel 是否被远程关闭
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
                if exit_code == -1 and channel.exit_status_ready():
                    exit_code = channel.recv_exit_status()
                logger.debug("Channel 被远程关闭，数据接收完毕")
                break
            
            # 长时间无数据活动检查
            if time.time() - last_activity_time > 1.0:
                if channel.exit_status_ready():
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
            
            # 检查全局超时
            if time.time() - start_time > timeout:
                logger.error(f"接收数据超时 ({timeout}秒)")
                raise TimeoutError(f"命令执行超过 {timeout} 秒")
            
            time.sleep(0.001)  # 从5ms减少到1ms，加快测试速度

        # 解码数据
        encoding = self._config.encoding
        stdout_text = stdout_data.decode(encoding, errors="replace")
        stderr_text = stderr_data.decode(encoding, errors="replace")
        
        if stdout_truncated:
            stdout_text += "\n[输出已截断 - 超过最大限制]"
        if stderr_truncated:
            stderr_text += "\n[错误输出已截断 - 超过最大限制]"
        
        logger.debug(f"数据接收完成: stdout={len(stdout_text)}字符, stderr={len(stderr_text)}字符, exit_code={exit_code}")
        return stdout_text, stderr_text, exit_code


import time
