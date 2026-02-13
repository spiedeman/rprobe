"""
智能通道接收器工厂模块

根据配置和平台自动选择最优的数据接收策略，
实现性能优化与兼容性的平衡。
"""
import logging
import sys
from typing import Optional, Tuple

# 从后端导入抽象类型
from src.backends.base import Channel, Transport

from src.config.models import SSHConfig, RecvMode
from src.receivers.channel_receiver import ChannelDataReceiver


logger = logging.getLogger(__name__)


class SmartChannelReceiver:
    """
    智能通道数据接收器
    
    根据配置自动选择最优的接收策略：
    - Linux/Mac: 优先使用 select 实现零 CPU 等待
    - Windows: 使用自适应轮询降低 CPU 占用
    - 可配置为使用原始模式保持向后兼容
    
    性能对比:
    - Select 模式: CPU 占用 ~0% (等待时)
    - 自适应轮询: CPU 占用 ~2-5% (等待时)
    - 原始轮询: CPU 占用 ~10-20% (等待时)
    """
    
    def __init__(self, config: SSHConfig):
        """
        初始化智能接收器
        
        Args:
            config: SSH 配置，包含 recv_mode 设置
        """
        self._config = config
        self._mode: RecvMode = self._select_mode()
        self._receiver = self._create_receiver()
        logger.debug(f"SmartChannelReceiver 初始化完成，模式: {self._mode}")
    
    def _select_mode(self) -> RecvMode:
        """
        根据配置和平台选择最优模式
        
        Returns:
            RecvMode: 选择的接收模式
        """
        mode = self._config.recv_mode
        
        if mode == RecvMode.AUTO:
            # 自动选择：非 Windows 使用 select，Windows 使用 adaptive
            if sys.platform != 'win32':
                mode = RecvMode.SELECT
                logger.debug("自动选择模式: select (非 Windows 平台)")
            else:
                mode = RecvMode.ADAPTIVE
                logger.debug("自动选择模式: adaptive (Windows 平台)")
        
        # 验证模式有效性
        valid_modes = [RecvMode.SELECT, RecvMode.ADAPTIVE, RecvMode.ORIGINAL]
        if mode not in valid_modes:
            logger.warning(f"无效的接收模式 '{mode}'，使用 original 模式")
            mode = RecvMode.ORIGINAL
        
        return mode
    
    def _create_receiver(self):
        """
        创建对应模式的接收器
        
        Returns:
            对应的接收器实例
        """
        if self._mode == RecvMode.SELECT:
            from .channel_receiver_optimized import OptimizedChannelDataReceiver
            return OptimizedChannelDataReceiver(self._config)
        elif self._mode == RecvMode.ADAPTIVE:
            from .channel_receiver_optimized import AdaptivePollingReceiver
            return AdaptivePollingReceiver(self._config)
        else:
            # ORIGINAL 模式
            return ChannelDataReceiver(self._config)
    
    def recv_all(
        self,
        channel: Channel,
        timeout: Optional[float] = None,
        transport: Optional[Transport] = None
    ) -> Tuple[str, str, int]:
        """
        智能接收通道所有数据
        
        根据配置的模式使用不同的接收策略：
        - select 模式: 使用非阻塞 + select 实现零 CPU 等待
        - adaptive 模式: 使用自适应轮询间隔
        - original 模式: 使用原始轮询实现
        
        Args:
            channel: SSH Channel 对象
            timeout: 命令执行总超时
            transport: SSH Transport 对象
            
        Returns:
            Tuple[str, str, int]: (stdout 文本, stderr 文本, exit_code)
        """
        timeout = timeout or self._config.command_timeout
        
        if self._mode == RecvMode.SELECT:
            # Select 模式使用 OptimizedChannelDataReceiver 的 recv_all_optimized
            try:
                return self._receiver.recv_all_optimized(channel, timeout, transport)
            except (TypeError, ValueError) as e:
                # select 失败（例如 mock 对象），回退到自适应模式
                logger.debug(f"Select 模式不可用 ({e})，回退到自适应轮询")
                from .channel_receiver_optimized import AdaptivePollingReceiver
                fallback_receiver = AdaptivePollingReceiver(self._config)
                return fallback_receiver.recv_all(channel, timeout, transport)
        elif self._mode == RecvMode.ADAPTIVE:
            # 自适应模式使用 AdaptivePollingReceiver 的 recv_all
            return self._receiver.recv_all(channel, timeout)
        else:
            # 原始模式使用 ChannelDataReceiver 的 recv_all
            return self._receiver.recv_all(channel, timeout, transport)
    
    @property
    def mode(self) -> RecvMode:
        """获取当前使用的接收模式"""
        return self._mode
    
    def get_performance_info(self) -> dict:
        """
        获取性能信息
        
        Returns:
            dict: 包含模式信息和预期性能的字典
        """
        mode_descriptions = {
            RecvMode.SELECT: {
                "name": "Select 模式",
                "description": "使用 select/poll 实现零 CPU 等待",
                "cpu_usage": "~0% (等待时)",
                "latency": "< 1ms",
                "platform": "Linux/Mac"
            },
            RecvMode.ADAPTIVE: {
                "name": "自适应轮询",
                "description": "根据数据到达频率自动调整轮询间隔",
                "cpu_usage": "~2-5% (等待时)",
                "latency": "1-50ms",
                "platform": "全平台"
            },
            RecvMode.ORIGINAL: {
                "name": "原始轮询",
                "description": "固定间隔轮询",
                "cpu_usage": "~10-20% (等待时)",
                "latency": "1ms",
                "platform": "全平台"
            }
        }
        
        info = mode_descriptions.get(self._mode, {}).copy()
        info["current_mode"] = self._mode.value
        info["platform"] = sys.platform
        info["config_mode"] = self._config.recv_mode.value
        
        return info


def create_receiver(config: SSHConfig) -> SmartChannelReceiver:
    """
    工厂函数：创建智能接收器
    
    Args:
        config: SSH 配置
        
    Returns:
        SmartChannelReceiver: 智能接收器实例
        
    Example:
        >>> config = SSHConfig(host="example.com", username="user", password="pass")
        >>> receiver = create_receiver(config)
        >>> print(f"使用模式: {receiver.mode}")
    """
    return SmartChannelReceiver(config)


def compare_modes():
    """
    打印各模式性能对比信息
    """
    print("=" * 60)
    print("SSH 数据接收模式性能对比")
    print("=" * 60)
    print()
    
    modes = [
        (RecvMode.SELECT, "Select/Poll 模式", "Linux/Mac", "~0%", "< 1ms"),
        (RecvMode.ADAPTIVE, "自适应轮询", "全平台", "~2-5%", "1-50ms"),
        (RecvMode.ORIGINAL, "原始轮询", "全平台", "~10-20%", "1ms"),
    ]
    
    print(f"{'模式':<15} {'平台':<12} {'CPU占用':<10} {'延迟':<10}")
    print("-" * 60)
    for mode, name, platform, cpu, latency in modes:
        print(f"{name:<15} {platform:<12} {cpu:<10} {latency:<10}")
    
    print()
    print("推荐配置:")
    print("  - 生产环境 (Linux/Mac): recv_mode='select'")
    print("  - Windows 环境: recv_mode='adaptive' 或 'auto'")
    print("  - 兼容性优先: recv_mode='original'")
    print("=" * 60)
