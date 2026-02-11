"""
连接池管理模块

提供SSH连接池管理，支持连接复用、健康检查和自动清理。

Features:
- 连接复用：减少连接建立开销
- 健康检查：自动检测和清理无效连接
- 连接限制：防止连接数过多
- 超时管理：支持获取连接超时
- 线程安全：支持多线程并发访问

Example:
    from src.pooling import ConnectionPool
    
    # 创建连接池
    pool = ConnectionPool(
        config=ssh_config,
        max_size=10,
        max_idle=300,
        max_age=3600
    )
    
    # 获取连接
    with pool.get_connection() as conn:
        result = conn.execute_command("ls -la")
    
    # 关闭连接池
    pool.close()
"""
import threading
import time
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from collections import deque
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed

import paramiko

from src.config.models import SSHConfig
from src.exceptions import PoolExhaustedError, PoolTimeoutError
from src.core.connection import ConnectionManager


logger = logging.getLogger(__name__)


@dataclass
class PooledConnection:
    """池化连接包装器"""
    connection: ConnectionManager
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    is_active: bool = True
    
    def mark_used(self) -> None:
        """标记连接被使用"""
        self.last_used = time.time()
        self.use_count += 1
    
    def is_expired(self, max_idle: float, max_age: float) -> bool:
        """检查连接是否过期"""
        now = time.time()
        idle_time = now - self.last_used
        age = now - self.created_at
        
        return idle_time > max_idle or age > max_age
    
    def is_healthy(self) -> bool:
        """检查连接是否健康"""
        return self.is_active and self.connection.is_connected
    
    def close(self) -> None:
        """关闭连接"""
        self.is_active = False
        try:
            self.connection.disconnect()
        except Exception as e:
            logger.warning(f"Error closing pooled connection: {e}")


class ConnectionPool:
    """
    SSH连接池
    
    管理SSH连接的复用和生命周期。
    """
    
    def __init__(
        self,
        config: SSHConfig,
        max_size: int = 10,
        min_size: int = 1,
        max_idle: float = 300.0,  # 5分钟
        max_age: float = 3600.0,  # 1小时
        acquire_timeout: float = 30.0,
        health_check_interval: float = 60.0,
        parallel_init: bool = True
    ):
        """
        初始化连接池
        
        Args:
            config: SSH配置
            max_size: 最大连接数
            min_size: 最小连接数（保留的连接数）
            max_idle: 最大空闲时间（秒）
            max_age: 最大连接寿命（秒）
            acquire_timeout: 获取连接超时时间（秒）
            health_check_interval: 健康检查间隔（秒）
            parallel_init: 是否并行初始化连接（默认True）
        """
        self._config = config
        self._max_size = max_size
        self._min_size = min_size
        self._max_idle = max_idle
        self._max_age = max_age
        self._acquire_timeout = acquire_timeout
        
        # 连接池
        self._pool: deque[PooledConnection] = deque()
        self._in_use: List[PooledConnection] = []
        
        # 同步原语
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        
        # 统计信息
        self._stats = {
            "created": 0,
            "reused": 0,
            "closed": 0,
            "expired": 0,
            "failed": 0
        }
        
        # 健康检查线程
        self._shutdown = False
        self._health_check_thread: Optional[threading.Thread] = None
        if health_check_interval > 0:
            self._health_check_thread = threading.Thread(
                target=self._health_check_loop,
                args=(health_check_interval,),
                daemon=True
            )
            self._health_check_thread.start()
        
        # 初始化最小连接数（串行或并行）
        if parallel_init and min_size > 1:
            self._initialize_min_connections_parallel()
        else:
            self._initialize_min_connections()
        
        logger.info(
            f"Connection pool created for {config.host} (max_size={max_size}, min_size={min_size}, parallel={parallel_init})"
        )
    
    def _initialize_min_connections(self) -> None:
        """初始化最小连接数（串行）"""
        for _ in range(self._min_size):
            try:
                conn = self._create_connection()
                self._pool.append(conn)
            except Exception as e:
                logger.warning(f"Failed to create initial connection: {e}")

    def _initialize_min_connections_parallel(self) -> None:
        """初始化最小连接数（并行）
        
        使用多线程并行创建多个连接，显著减少初始化时间。
        适用于 min_size > 1 的场景。
        """
        # 限制并发数，避免过多线程
        max_workers = min(self._min_size, 10)
        
        successful_connections = []
        failed_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有创建任务
            future_to_index = {
                executor.submit(self._create_connection_safe): i
                for i in range(self._min_size)
            }
            
            # 收集结果
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    conn = future.result()
                    if conn:
                        successful_connections.append(conn)
                        logger.debug(
                            f"Parallel connection {index + 1}/{self._min_size} created successfully"
                        )
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"Parallel connection {index + 1} failed: {e}")
        
        # 将成功创建的连接加入连接池
        for conn in successful_connections:
            self._pool.append(conn)
        
        # 如果所有连接都创建失败，记录错误
        if len(successful_connections) == 0 and self._min_size > 0:
            logger.error(f"All {self._min_size} parallel connection attempts failed")
        
        logger.info(
            f"Parallel initialization completed: {len(successful_connections)}/{self._min_size} "
            f"connections created ({failed_count} failed)"
        )

    def _create_connection_safe(self) -> Optional[PooledConnection]:
        """线程安全地创建连接
        
        Returns:
            PooledConnection: 成功创建的连接，失败返回 None
        """
        try:
            return self._create_connection()
        except Exception as e:
            logger.debug(f"Connection creation failed: {e}")
            return None

    def _create_connection(self) -> PooledConnection:
        """创建新连接"""
        connection = ConnectionManager(self._config)
        connection.connect()
        
        pooled = PooledConnection(connection=connection)
        self._stats["created"] += 1
        
        logger.debug(
            f"Created new connection for {self._config.host} (pool_size={len(self._pool)})"
        )
        
        return pooled
    
    @contextmanager
    def get_connection(self, timeout: Optional[float] = None):
        """
        获取连接（上下文管理器）
        
        Args:
            timeout: 获取连接超时时间（秒）
            
        Yields:
            ConnectionManager: 连接管理器
            
        Raises:
            PoolExhaustedError: 连接池耗尽
            PoolTimeoutError: 获取连接超时
        """
        pooled_conn = self._acquire(timeout)
        try:
            yield pooled_conn.connection
        finally:
            self._release(pooled_conn)
    
    def _acquire(self, timeout: Optional[float] = None) -> PooledConnection:
        """
        获取连接
        
        Args:
            timeout: 超时时间
            
        Returns:
            PooledConnection: 池化连接
        """
        timeout = timeout or self._acquire_timeout
        deadline = time.time() + timeout
        
        with self._condition:
            while True:
                # 1. 尝试从池中获取可用连接
                while self._pool:
                    pooled = self._pool.popleft()
                    
                    if pooled.is_healthy() and not pooled.is_expired(self._max_idle, self._max_age):
                        # 健康检查通过
                        pooled.mark_used()
                        self._in_use.append(pooled)
                        self._stats["reused"] += 1
                        
                        logger.debug(
                            f"Reusing connection from pool for {self._config.host} (pool_size={len(self._pool)}, in_use={len(self._in_use)})"
                        )
                        return pooled
                    else:
                        # 连接不健康或已过期，关闭
                        pooled.close()
                        self._stats["expired"] += 1
                
                # 2. 如果池为空且未达到最大连接数，创建新连接
                total_connections = len(self._pool) + len(self._in_use)
                if total_connections < self._max_size:
                    try:
                        pooled = self._create_connection()
                        pooled.mark_used()
                        self._in_use.append(pooled)
                        return pooled
                    except Exception as e:
                        logger.error(f"Failed to create connection: {e}")
                        self._stats["failed"] += 1
                        raise
                
                # 3. 等待连接释放
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise PoolTimeoutError(timeout, self._max_size)
                
                self._condition.wait(timeout=remaining)
    
    def _release(self, pooled: PooledConnection) -> None:
        """
        释放连接
        
        Args:
            pooled: 池化连接
        """
        with self._lock:
            self._in_use.remove(pooled)
            
            if pooled.is_healthy() and not pooled.is_expired(self._max_idle, self._max_age):
                # 连接健康，放回池中
                self._pool.append(pooled)
                logger.debug(
                    f"Returned connection to pool for {self._config.host} (pool_size={len(self._pool)})"
                )
            else:
                # 连接不健康或过期，关闭
                pooled.close()
                self._stats["closed"] += 1
            
            # 通知等待的线程
            self._condition.notify()
    
    def _health_check_loop(self, interval: float) -> None:
        """
        健康检查循环
        
        Args:
            interval: 检查间隔
        """
        while not self._shutdown:
            try:
                time.sleep(interval)
                self._cleanup_expired()
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    def _cleanup_expired(self) -> None:
        """清理过期连接"""
        with self._lock:
            # 清理池中过期连接
            expired = []
            kept = []
            
            for pooled in self._pool:
                if pooled.is_expired(self._max_idle, self._max_age) or not pooled.is_healthy():
                    expired.append(pooled)
                else:
                    kept.append(pooled)
            
            self._pool = deque(kept)
            
            for pooled in expired:
                pooled.close()
                self._stats["expired"] += 1
            
            if expired:
                logger.debug(
                    f"Cleaned up {len(expired)} expired connections for {self._config.host}"
                )
    
    def close(self, timeout: float = 10.0) -> None:
        """
        关闭连接池
        
        Args:
            timeout: 关闭超时时间
        """
        logger.info(f"Closing connection pool for {self._config.host}")

        self._shutdown = True
        
        # 停止健康检查线程
        if self._health_check_thread and self._health_check_thread.is_alive():
            self._health_check_thread.join(timeout=timeout)
        
        # 并行关闭所有连接
        with self._lock:
            all_connections = list(self._pool) + list(self._in_use)
            self._pool.clear()
            self._in_use.clear()
            
            # 并行关闭连接以提高性能
            if all_connections:
                self._close_connections_parallel(all_connections, timeout)
        
        logger.info(f"Connection pool closed for {self._config.host}")
    
    def _close_connections_parallel(self, connections: List[PooledConnection], timeout: float) -> None:
        """
        并行关闭连接
        
        Args:
            connections: 需要关闭的连接列表
            timeout: 总超时时间
        """
        if not connections:
            return
        
        # 限制并发线程数
        max_workers = min(len(connections), 10)
        failed_count = 0
        start_time = time.time()
        
        # 计算每个连接的超时时间（平均分配总超时）
        single_timeout = timeout / len(connections) if connections else timeout
        single_timeout = min(single_timeout, 2.0)  # 最多2秒
        
        def close_single_connection(pooled: PooledConnection) -> None:
            """关闭单个连接，带超时"""
            import threading
            
            result = {"success": False, "error": None}
            
            def do_close():
                try:
                    pooled.close()
                    result["success"] = True
                except Exception as e:
                    result["error"] = e
            
            # 在新线程中执行关闭，带超时
            close_thread = threading.Thread(target=do_close)
            close_thread.daemon = True
            close_thread.start()
            close_thread.join(timeout=single_timeout)
            
            if close_thread.is_alive():
                # 超时，强制标记为非活跃
                pooled.is_active = False
                raise TimeoutError(f"Connection close timeout after {single_timeout}s")
            
            if result["error"]:
                raise result["error"]
        
        # 使用线程池并行关闭
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(close_single_connection, conn): conn 
                      for conn in connections}
            
            # 等待所有任务完成或超时
            remaining_timeout = timeout
            for future in list(futures.keys()):
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    logger.warning(f"Overall close timeout after {elapsed:.2f}s")
                    break
                
                try:
                    # 等待剩余时间
                    wait_time = min(remaining_timeout - elapsed, single_timeout)
                    future.result(timeout=max(wait_time, 0.1))
                except TimeoutError:
                    failed_count += 1
                    logger.warning(f"Connection close timeout")
                    # 强制标记为非活跃
                    futures[future].is_active = False
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"Failed to close connection: {e}")
        
        elapsed = time.time() - start_time
        if failed_count > 0:
            logger.warning(f"Failed to close {failed_count}/{len(connections)} connections in {elapsed:.2f}s")
        else:
            logger.debug(f"Closed {len(connections)} connections in {elapsed:.2f}s")
    
    @property
    def stats(self) -> Dict:
        """获取连接池统计信息"""
        with self._lock:
            return {
                **self._stats,
                "pool_size": len(self._pool),
                "in_use": len(self._in_use),
                "total": len(self._pool) + len(self._in_use),
                "max_size": self._max_size
            }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PoolManager:
    """
    连接池管理器
    
    管理多个配置对应的连接池。
    """
    
    def __init__(self):
        self._pools: Dict[str, ConnectionPool] = {}
        self._lock = threading.RLock()
    
    def get_or_create_pool(
        self,
        config: SSHConfig,
        **pool_kwargs
    ) -> ConnectionPool:
        """
        获取或创建连接池
        
        Args:
            config: SSH配置
            **pool_kwargs: 连接池参数
            
        Returns:
            ConnectionPool: 连接池
        """
        pool_key = f"{config.username}@{config.host}:{config.port}"
        
        with self._lock:
            if pool_key not in self._pools:
                self._pools[pool_key] = ConnectionPool(config, **pool_kwargs)
            
            return self._pools[pool_key]
    
    def close_all(self) -> None:
        """关闭所有连接池"""
        with self._lock:
            for pool_key, pool in list(self._pools.items()):
                try:
                    pool.close()
                except Exception as e:
                    logger.error(f"Error closing pool {pool_key}: {e}")
            
            self._pools.clear()
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有连接池统计信息"""
        with self._lock:
            return {key: pool.stats for key, pool in self._pools.items()}


# 全局连接池管理器
_global_pool_manager = PoolManager()


def get_pool_manager() -> PoolManager:
    """获取全局连接池管理器"""
    return _global_pool_manager
