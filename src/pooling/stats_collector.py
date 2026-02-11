"""
连接池统计收集器模块

提供独立的统计信息收集功能，与连接池业务逻辑解耦。

Example:
    from src.pooling.stats_collector import PoolStatsCollector
    
    # 创建统计收集器
    stats = PoolStatsCollector()
    
    # 记录事件
    stats.record_connection_created()
    stats.record_connection_reused()
    stats.record_acquire_time(0.5)
    
    # 获取统计信息
    print(stats.get_stats())
"""
import time
import threading
from typing import Dict, Optional, List
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PoolMetrics:
    """连接池指标数据类"""
    # 连接计数
    created: int = 0
    reused: int = 0
    returned: int = 0
    closed: int = 0
    expired: int = 0
    failed: int = 0
    
    # 初始化统计
    init_succeeded: int = 0
    init_failed: int = 0
    
    # 健康检查统计
    health_checks: int = 0
    health_check_passed: int = 0
    health_check_failed: int = 0
    
    # 关闭统计
    closed_during_shutdown: int = 0
    
    # 峰值使用
    peak_in_use: int = 0
    
    # 等待统计
    waits: int = 0
    total_wait_time: float = 0.0
    
    # 时间戳
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "created": self.created,
            "reused": self.reused,
            "returned": self.returned,
            "closed": self.closed,
            "expired": self.expired,
            "failed": self.failed,
            "init_succeeded": self.init_succeeded,
            "init_failed": self.init_failed,
            "health_checks": self.health_checks,
            "health_check_passed": self.health_check_passed,
            "health_check_failed": self.health_check_failed,
            "closed_during_shutdown": self.closed_during_shutdown,
            "peak_in_use": self.peak_in_use,
            "waits": self.waits,
            "total_wait_time": self.total_wait_time,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
        }


class PoolStatsCollector:
    """
    连接池统计收集器
    
    独立收集连接池的各种统计信息，与业务逻辑解耦。
    
    Features:
    - 线程安全：所有操作使用锁保护
    - 可配置：可以启用/禁用统计
    - 可扩展：支持自定义指标
    - 低开销：使用 deque 限制历史数据大小
    """
    
    def __init__(self, enabled: bool = True, max_history: int = 100):
        """
        初始化统计收集器
        
        Args:
            enabled: 是否启用统计
            max_history: 历史数据最大保留数量
        """
        self._enabled = enabled
        self._lock = threading.RLock()
        self._metrics = PoolMetrics()
        
        # 性能数据历史
        self._max_history = max_history
        self._acquire_times: deque = deque(maxlen=max_history)
        self._wait_times: deque = deque(maxlen=max_history)
        self._connection_lifetimes: deque = deque(maxlen=max_history)
    
    @property
    def enabled(self) -> bool:
        """检查统计是否启用"""
        return self._enabled
    
    def disable(self) -> None:
        """禁用统计"""
        self._enabled = False
    
    def enable(self) -> None:
        """启用统计"""
        self._enabled = True
    
    # ========== 事件记录方法 ==========
    
    def record_connection_created(self) -> None:
        """记录连接创建"""
        if not self._enabled:
            return
        with self._lock:
            self._metrics.created += 1
            self._metrics.last_activity = time.time()
    
    def record_connection_reused(self) -> None:
        """记录连接复用"""
        if not self._enabled:
            return
        with self._lock:
            self._metrics.reused += 1
            self._metrics.last_activity = time.time()
    
    def record_connection_returned(self) -> None:
        """记录连接归还"""
        if not self._enabled:
            return
        with self._lock:
            self._metrics.returned += 1
            self._metrics.last_activity = time.time()
    
    def record_connection_closed(self) -> None:
        """记录连接关闭"""
        if not self._enabled:
            return
        with self._lock:
            self._metrics.closed += 1
            self._metrics.last_activity = time.time()
    
    def record_connection_expired(self) -> None:
        """记录连接过期"""
        if not self._enabled:
            return
        with self._lock:
            self._metrics.expired += 1
    
    def record_connection_failed(self) -> None:
        """记录连接失败"""
        if not self._enabled:
            return
        with self._lock:
            self._metrics.failed += 1
    
    def record_init_succeeded(self, count: int = 1) -> None:
        """记录初始化成功"""
        if not self._enabled:
            return
        with self._lock:
            self._metrics.init_succeeded += count
    
    def record_init_failed(self, count: int = 1) -> None:
        """记录初始化失败"""
        if not self._enabled:
            return
        with self._lock:
            self._metrics.init_failed += count
    
    def record_health_check(self, passed: bool) -> None:
        """记录健康检查结果"""
        if not self._enabled:
            return
        with self._lock:
            self._metrics.health_checks += 1
            if passed:
                self._metrics.health_check_passed += 1
            else:
                self._metrics.health_check_failed += 1
    
    def record_shutdown_close(self, count: int = 1) -> None:
        """记录关闭时关闭的连接"""
        if not self._enabled:
            return
        with self._lock:
            self._metrics.closed_during_shutdown += count
    
    def record_acquire_time(self, acquire_time: float) -> None:
        """记录连接获取时间"""
        if not self._enabled:
            return
        with self._lock:
            self._acquire_times.append(acquire_time)
            self._metrics.last_activity = time.time()
    
    def record_wait_time(self, wait_time: float) -> None:
        """记录等待时间"""
        if not self._enabled:
            return
        with self._lock:
            self._wait_times.append(wait_time)
            self._metrics.waits += 1
            self._metrics.total_wait_time += wait_time
    
    def record_connection_lifetime(self, lifetime: float) -> None:
        """记录连接生命周期"""
        if not self._enabled:
            return
        with self._lock:
            self._connection_lifetimes.append(lifetime)
    
    def update_peak_in_use(self, current_in_use: int) -> None:
        """更新峰值使用数"""
        if not self._enabled:
            return
        with self._lock:
            if current_in_use > self._metrics.peak_in_use:
                self._metrics.peak_in_use = current_in_use
    
    # ========== 统计查询方法 ==========
    
    def get_metrics(self) -> PoolMetrics:
        """获取指标数据（副本）"""
        with self._lock:
            # 返回深拷贝，防止外部修改
            return PoolMetrics(**self._metrics.to_dict())
    
    def get_acquire_times(self) -> List[float]:
        """获取获取时间历史"""
        with self._lock:
            return list(self._acquire_times)
    
    def get_wait_times(self) -> List[float]:
        """获取等待时间历史"""
        with self._lock:
            return list(self._wait_times)
    
    def get_lifetimes(self) -> List[float]:
        """获取生命周期历史"""
        with self._lock:
            return list(self._connection_lifetimes)
    
    def get_stats(self, current_pool_size: int = 0, current_in_use: int = 0,
                  max_size: int = 0) -> Dict:
        """
        获取完整统计信息
        
        Args:
            current_pool_size: 当前池中连接数
            current_in_use: 当前使用中的连接数
            max_size: 最大连接数
            
        Returns:
            Dict 包含完整统计信息
        """
        if not self._enabled:
            return {"enabled": False}
        
        with self._lock:
            metrics = self._metrics
            total = current_pool_size + current_in_use
            
            # 计算使用率
            utilization_rate = (current_in_use / max_size * 100) if max_size > 0 else 0
            pool_usage_rate = (total / max_size * 100) if max_size > 0 else 0
            
            # 计算平均等待时间
            avg_wait_time = (metrics.total_wait_time / metrics.waits 
                           if metrics.waits > 0 else 0.0)
            
            # 计算获取时间统计
            avg_acquire_time = (sum(self._acquire_times) / len(self._acquire_times) 
                              if self._acquire_times else 0.0)
            max_acquire_time = max(self._acquire_times) if self._acquire_times else 0.0
            
            # 计算最近等待时间
            avg_wait_time_recent = (sum(self._wait_times) / len(self._wait_times) 
                                   if self._wait_times else 0.0)
            
            # 计算派生指标
            init_attempts = metrics.init_succeeded + metrics.init_failed
            init_success_rate = (metrics.init_succeeded / init_attempts * 100 
                               if init_attempts > 0 else 0.0)
            
            health_check_rate = (metrics.health_check_passed / metrics.health_checks * 100 
                               if metrics.health_checks > 0 else 0.0)
            
            total_acquired = metrics.created + metrics.reused
            reuse_rate = (metrics.reused / total_acquired * 100 
                         if total_acquired > 0 else 0.0)
            
            avg_lifetime = (sum(self._connection_lifetimes) / len(self._connection_lifetimes) 
                          if self._connection_lifetimes else 0.0)
            
            # 运行时间
            uptime_seconds = time.time() - metrics.created_at
            uptime_readable = self._format_uptime(uptime_seconds)
            
            # 格式化时间戳
            created_at_readable = datetime.fromtimestamp(metrics.created_at).strftime("%Y-%m-%d %H:%M:%S")
            last_activity_readable = self._format_relative_time(metrics.last_activity)
            
            return {
                **metrics.to_dict(),
                "pool_size": current_pool_size,
                "in_use": current_in_use,
                "total": total,
                "max_size": max_size,
                "utilization_rate": round(utilization_rate, 2),
                "pool_usage_rate": round(pool_usage_rate, 2),
                "init_success_rate": round(init_success_rate, 2),
                "health_check_rate": round(health_check_rate, 2),
                "reuse_rate": round(reuse_rate, 2),
                "avg_lifetime": round(avg_lifetime, 2),
                "avg_wait_time": round(avg_wait_time, 3),
                "avg_wait_time_recent": round(avg_wait_time_recent, 3),
                "avg_acquire_time": round(avg_acquire_time, 3),
                "max_acquire_time": round(max_acquire_time, 3),
                "acquire_count": len(self._acquire_times),
                "uptime": uptime_readable,
                "uptime_seconds": round(uptime_seconds, 1),
                "created_at_readable": created_at_readable,
                "last_activity_readable": last_activity_readable,
            }
    
    def reset(self) -> None:
        """重置所有统计"""
        with self._lock:
            self._metrics = PoolMetrics()
            self._acquire_times.clear()
            self._wait_times.clear()
            self._connection_lifetimes.clear()
    
    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """格式化运行时间"""
        if seconds < 60:
            return f"{int(seconds)}s"
        
        minutes, secs = divmod(int(seconds), 60)
        if minutes < 60:
            return f"{minutes}m{secs}s"
        
        hours, minutes = divmod(minutes, 60)
        if hours < 24:
            return f"{hours}h{minutes}m"
        
        days, hours = divmod(hours, 24)
        return f"{days}d{hours}h"
    
    @staticmethod
    def _format_relative_time(timestamp: float) -> str:
        """格式化相对时间"""
        diff = time.time() - timestamp
        
        if diff < 5:
            return "刚刚"
        elif diff < 60:
            return f"{int(diff)}秒前"
        elif diff < 3600:
            minutes, _ = divmod(int(diff), 60)
            return f"{minutes}分钟前"
        elif diff < 86400:
            hours, _ = divmod(int(diff), 3600)
            return f"{hours}小时前"
        else:
            days, _ = divmod(int(diff), 86400)
            return f"{days}天前"
