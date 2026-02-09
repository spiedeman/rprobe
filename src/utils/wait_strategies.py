"""
智能等待策略模块
提供自适应的等待机制，平衡响应速度和CPU占用

设计原则：
1. 开始时快速检查（低延迟响应）
2. 逐渐延长等待间隔（减少CPU占用）
3. 收到数据后立即处理（保持响应性）
"""
import time
from typing import Optional, Callable, Any


class AdaptiveWaitStrategy:
    """
    自适应等待策略
    
    根据等待时间动态调整检查间隔，实现：
    - 快速启动：开始时频繁检查（1ms-10ms）
    - 渐进放缓：逐渐增加到较长间隔（50ms-100ms）
    - 上限保护：最大等待间隔不超过上限
    
    Example:
        waiter = AdaptiveWaitStrategy(
            initial_wait=0.001,      # 1ms
            max_wait=0.05,           # 50ms
            growth_factor=1.5        # 每次增长50%
        )
        
        while not condition():
            waiter.wait()
    """
    
    def __init__(
        self,
        initial_wait: float = 0.001,      # 1ms
        max_wait: float = 0.05,            # 50ms
        growth_factor: float = 1.5,        # 50%增长
        reset_on_call: bool = True         # 每次wait后是否重置
    ):
        """
        初始化等待策略
        
        Args:
            initial_wait: 初始等待时间（秒）
            max_wait: 最大等待时间（秒）
            growth_factor: 增长因子（>1.0）
            reset_on_call: 是否在每次wait后重置到初始值
        """
        self.initial_wait = initial_wait
        self.max_wait = max_wait
        self.growth_factor = growth_factor
        self.reset_on_call = reset_on_call
        
        self._current_wait = initial_wait
        self._wait_count = 0
    
    def wait(self) -> float:
        """
        执行等待并返回实际等待时间
        
        Returns:
            float: 实际等待的秒数
        """
        time.sleep(self._current_wait)
        actual_wait = self._current_wait
        
        self._wait_count += 1
        
        # 计算下一次等待时间
        self._current_wait = min(
            self._current_wait * self.growth_factor,
            self.max_wait
        )
        
        return actual_wait
    
    def reset(self) -> None:
        """重置等待时间到初始值"""
        self._current_wait = self.initial_wait
    
    @property
    def current_wait(self) -> float:
        """获取当前等待时间"""
        return self._current_wait
    
    @property
    def wait_count(self) -> int:
        """获取已执行等待的次数"""
        return self._wait_count


class BlockingWaitStrategy:
    """
    阻塞式等待策略
    
    使用 paramiko Channel 的阻塞读取功能，
    让操作系统处理等待，零CPU占用。
    
    适用于：
    - 网络延迟较高的场景
    - CPU资源敏感的环境
    - 不需要超低延迟的场景
    """
    
    def __init__(self, timeout: float):
        """
        初始化阻塞等待策略
        
        Args:
            timeout: 读取超时时间（秒）
        """
        self.timeout = timeout
    
    def wait_for_data(
        self,
        recv_func: Callable[[int], bytes],
        timeout: Optional[float] = None
    ) -> Optional[bytes]:
        """
        阻塞等待数据到达
        
        Args:
            recv_func: 接收数据的函数（如 channel.recv）
            timeout: 可选的超时时间，覆盖默认值
            
        Returns:
            Optional[bytes]: 接收到的数据，超时返回 None
        """
        timeout = timeout or self.timeout
        
        try:
            # 设置超时时间
            # 注意：这里假设 recv_func 所属的对象有 settimeout 方法
            # 实际使用时需要在外部设置
            return recv_func(4096)
        except Exception:
            return None


class HybridWaitStrategy:
    """
    混合等待策略（推荐用于生产环境）
    
    结合轮询和等待的优势：
    1. 使用短间隔快速轮询（1-10ms）
    2. 多次轮询无数据后，使用阻塞等待（50-100ms）
    3. 有数据时立即处理
    
    这种策略在保持响应性的同时，显著降低CPU占用。
    """
    
    def __init__(
        self,
        poll_interval: float = 0.01,      # 10ms 轮询
        blocking_threshold: int = 10,      # 10次轮询后转阻塞
        blocking_timeout: float = 0.1      # 100ms 阻塞超时
    ):
        """
        初始化混合等待策略
        
        Args:
            poll_interval: 轮询间隔（秒）
            blocking_threshold: 转为阻塞前的轮询次数
            blocking_timeout: 阻塞等待超时（秒）
        """
        self.poll_interval = poll_interval
        self.blocking_threshold = blocking_threshold
        self.blocking_timeout = blocking_timeout
        
        self._poll_count = 0
    
    def wait(self, has_data: Callable[[], bool]) -> bool:
        """
        执行智能等待
        
        Args:
            has_data: 检查是否有数据的函数
            
        Returns:
            bool: 是否有数据
        """
        # 检查是否有数据
        if has_data():
            self._poll_count = 0
            return True
        
        self._poll_count += 1
        
        if self._poll_count < self.blocking_threshold:
            # 短轮询阶段
            time.sleep(self.poll_interval)
        else:
            # 阻塞等待阶段
            time.sleep(self.blocking_timeout)
        
        return has_data()
    
    def reset(self) -> None:
        """重置轮询计数"""
        self._poll_count = 0


# 便捷函数：计算平均等待间隔
def calculate_average_wait(
    strategy: AdaptiveWaitStrategy,
    iterations: int = 100
) -> float:
    """
    计算给定迭代次数的平均等待时间
    
    Args:
        strategy: 等待策略
        iterations: 迭代次数
        
    Returns:
        float: 平均等待时间（秒）
    """
    # 模拟等待（不实际等待）
    total_wait = 0.0
    current = strategy.initial_wait
    
    for _ in range(iterations):
        total_wait += current
        current = min(current * strategy.growth_factor, strategy.max_wait)
    
    return total_wait / iterations
