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
import uuid
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
from collections import deque
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed, wait

from src.config.models import SSHConfig
from src.exceptions import PoolTimeoutError
from src.core.connection import ConnectionManager
from src.pooling.stats_collector import PoolStatsCollector

logger = logging.getLogger(__name__)


@dataclass
class PooledConnection:
    """池化连接包装器"""

    connection: ConnectionManager
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
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
        parallel_init: bool = True,
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
        self._health_check_interval = health_check_interval
        self._parallel_init = parallel_init

        # 连接池
        self._pool: deque[PooledConnection] = deque()
        self._in_use: List[PooledConnection] = []

        # 同步原语
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)

        # 统计收集器（解耦统计逻辑）
        self._stats_collector = PoolStatsCollector(enabled=True, max_history=100)

        # 健康检查线程
        self._shutdown = False
        self._closed = False
        self._health_check_thread: Optional[threading.Thread] = None
        if health_check_interval > 0:
            self._health_check_thread = threading.Thread(
                target=self._health_check_loop, args=(health_check_interval,), daemon=True
            )
            self._health_check_thread.start()

        # 初始化最小连接数（串行或并行）
        if parallel_init and min_size > 1:
            self._initialize_min_connections_parallel()
        else:
            self._initialize_min_connections()

        logger.info(
            f"Connection pool created for {config.host} "
            f"(max_size={max_size}, min_size={min_size}, parallel={parallel_init})"
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
                executor.submit(self._create_connection_safe): i for i in range(self._min_size)
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

        # 记录初始化统计
        self._stats_collector.record_init_succeeded(len(successful_connections))
        self._stats_collector.record_init_failed(failed_count)

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
        self._stats_collector.record_connection_created()

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
            PoolTimeoutError: 获取连接超时
            RuntimeError: 连接池已关闭
        """
        if self._closed:
            raise RuntimeError("Connection pool has been closed. Please create a new instance.")

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

        Raises:
            RuntimeError: 连接池已关闭
        """
        if self._closed:
            raise RuntimeError("Connection pool has been closed. Please create a new instance.")

        timeout = timeout or self._acquire_timeout
        deadline = time.time() + timeout
        start_time = time.time()
        waited = False

        with self._condition:
            while True:
                # 1. 尝试从池中获取可用连接
                while self._pool:
                    pooled = self._pool.popleft()

                    if pooled.is_healthy() and not pooled.is_expired(self._max_idle, self._max_age):
                        # 健康检查通过
                        pooled.mark_used()
                        self._in_use.append(pooled)
                        self._stats_collector.record_connection_reused()

                        # 更新峰值使用
                        current_in_use = len(self._in_use)
                        self._stats_collector.update_peak_in_use(current_in_use)

                        # 记录获取时间
                        acquire_time = time.time() - start_time
                        self._stats_collector.record_acquire_time(acquire_time)

                        # 记录等待时间（如果有等待）
                        if waited:
                            wait_time = acquire_time
                            self._stats_collector.record_wait_time(wait_time)

                        logger.debug(
                            f"Reusing connection from pool for {self._config.host} "
                            f"(pool_size={len(self._pool)}, in_use={len(self._in_use)})"
                        )
                        return pooled
                    else:
                        # 连接不健康或已过期，关闭
                        pooled.close()
                        self._stats_collector.record_connection_expired()

                # 2. 如果池为空且未达到最大连接数，创建新连接
                total_connections = len(self._pool) + len(self._in_use)
                if total_connections < self._max_size:
                    try:
                        pooled = self._create_connection()
                        pooled.mark_used()
                        self._in_use.append(pooled)

                        # 更新峰值使用
                        current_in_use = len(self._in_use)
                        self._stats_collector.update_peak_in_use(current_in_use)

                        # 记录获取时间
                        acquire_time = time.time() - start_time
                        self._stats_collector.record_acquire_time(acquire_time)

                        # 记录等待时间（如果有等待）
                        if waited:
                            wait_time = acquire_time
                            self._stats_collector.record_wait_time(wait_time)

                        return pooled
                    except Exception as e:
                        logger.error(f"Failed to create connection: {e}")
                        self._stats_collector.record_connection_failed()
                        raise

                # 3. 等待连接释放
                waited = True
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise PoolTimeoutError(timeout, self._max_size)

                wait_start = time.time()
                self._condition.wait(timeout=remaining)
                self._stats_collector.record_wait_time(time.time() - wait_start)

    def _release(self, pooled: PooledConnection) -> None:
        """
        释放连接

        Args:
            pooled: 池化连接
        """
        with self._lock:
            # 检查连接是否已经在使用中列表中，避免重复释放
            if pooled not in self._in_use:
                logger.debug(f"Connection {id(pooled)} already released or not in use")
                return
            self._in_use.remove(pooled)

            if pooled.is_healthy() and not pooled.is_expired(self._max_idle, self._max_age):
                # 连接健康，放回池中
                self._pool.append(pooled)
                self._stats_collector.record_connection_returned()

                logger.debug(
                    f"Returned connection to pool for {self._config.host} "
                    f"(pool_size={len(self._pool)})"
                )
            else:
                # 连接不健康或过期，关闭
                pooled.close()
                self._stats_collector.record_connection_closed()

                # 记录连接生命周期
                lifetime = time.time() - pooled.created_at
                self._stats_collector.record_connection_lifetime(lifetime)

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
                # 使用条件变量的 wait 替代 sleep，可被提前唤醒
                with self._condition:
                    self._condition.wait(timeout=interval)

                # 检查是否需要退出
                if self._shutdown:
                    break

                self._cleanup_expired()
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

    def _cleanup_expired(self) -> None:
        """清理过期连接"""
        # 如果连接池已关闭，跳过清理
        if self._closed or self._shutdown:
            return

        with self._lock:
            # 清理池中过期连接
            expired = []
            kept = []

            for pooled in self._pool:
                self._stats_collector.record_health_check(passed=False)
                if pooled.is_expired(self._max_idle, self._max_age) or not pooled.is_healthy():
                    expired.append(pooled)

                    # 记录连接生命周期
                    lifetime = time.time() - pooled.created_at
                    self._stats_collector.record_connection_lifetime(lifetime)
                else:
                    kept.append(pooled)
                    self._stats_collector.record_health_check(passed=True)

            self._pool = deque(kept)

            # 关闭过期连接（但不在 _in_use 中的）
            for pooled in expired:
                if pooled not in self._in_use:
                    try:
                        pooled.close()
                        self._stats_collector.record_connection_expired()
                    except Exception as e:
                        logger.debug(f"关闭过期连接时出错: {e}")

            if expired:
                logger.debug(
                    f"Cleaned up {len(expired)} expired connections for {self._config.host}"
                )

    def close(self, timeout: float = 10.0) -> None:
        """
        关闭连接池中的所有连接

        关闭后连接池对象保留，可以通过 reset() 方法重新初始化后复用。

        Args:
            timeout: 关闭超时时间
        """
        logger.info(f"Closing connection pool for {self._config.host}")

        # 标记为已关闭，防止新的连接请求
        self._closed = True
        self._shutdown = True

        # 唤醒健康检查线程，让它立即退出（通过条件变量）
        with self._condition:
            self._condition.notify_all()

        # 等待健康检查线程退出（极短超时，因为线程已被唤醒）
        thread = self._health_check_thread
        if thread and thread.is_alive():
            thread.join(timeout=0.1)
            # 清理线程引用
            if self._health_check_thread is thread and not thread.is_alive():
                self._health_check_thread = None

        # 并行关闭所有连接
        with self._lock:
            all_connections = list(self._pool) + list(self._in_use)
            connection_count = len(all_connections)
            self._pool.clear()
            self._in_use.clear()

            # 并行关闭连接以提高性能
            if all_connections:
                self._close_connections_parallel(all_connections, timeout)
                self._stats_collector.record_shutdown_close(connection_count)

        logger.info(f"Connection pool closed for {self._config.host}")

    def reset(self) -> None:
        """
        重置连接池，模拟新建连接池的行为

        关闭现有连接（如果有），然后重新初始化连接池。
        重置后连接池恢复到初始状态，可以正常使用。
        """
        logger.info(f"Resetting connection pool for {self._config.host}")

        # 先关闭现有连接（如果池子还在运行）
        if not self._closed:
            self.close()

        # 重置状态
        with self._lock:
            self._closed = False
            self._shutdown = False

            # 重置统计收集器
            self._stats_collector.reset()

            # 重新创建连接池数据结构
            self._pool.clear()
            self._in_use.clear()

            # 重新启动健康检查线程
            if self._health_check_interval > 0:
                self._health_check_thread = threading.Thread(
                    target=self._health_check_loop, args=(self._health_check_interval,), daemon=True
                )
                self._health_check_thread.start()

            # 重新初始化最小连接数
            if self._parallel_init and self._min_size > 1:
                self._initialize_min_connections_parallel()
            else:
                self._initialize_min_connections()

        logger.info(f"Connection pool reset completed for {self._config.host}")

    def _close_connections_parallel(
        self, connections: List[PooledConnection], timeout: float
    ) -> None:
        """
        关闭连接（串行方式以避免并发问题）

        Args:
            connections: 需要关闭的连接列表
            timeout: 总超时时间
        """
        if not connections:
            return

        failed_count = 0
        start_time = time.time()
        deadline = start_time + timeout

        # 串行关闭连接，避免并发问题
        for conn in connections:
            if time.time() > deadline:
                logger.warning(
                    f"关闭连接超时，剩余 {len(connections) - connections.index(conn)} 个连接未关闭"
                )
                break

            try:
                # 标记为非活跃
                conn.is_active = False
                conn.close()
            except Exception as e:
                failed_count += 1
                logger.debug(f"关闭连接失败: {e}")

        elapsed = time.time() - start_time
        success_count = len(connections) - failed_count
        if failed_count > 0:
            logger.warning(
                f"Closed {success_count}/{len(connections)} connections in {elapsed:.2f}s "
                f"({failed_count} failed)"
            )
        else:
            logger.debug(f"Closed {len(connections)} connections in {elapsed:.2f}s")

    def _format_uptime(self, seconds: float) -> str:
        """将秒数格式化为人类可读的 uptime 字符串

        使用 divmod 优化计算，比多次除法和取模更高效。

        Args:
            seconds: 秒数

        Returns:
            str: 格式如 "2h15m30s" 或 "5m20s" 或 "30s"
        """
        if seconds < 60:
            return f"{int(seconds)}s"

        # 使用 divmod 一次性计算分钟和秒
        minutes, secs = divmod(int(seconds), 60)
        if minutes < 60:
            return f"{minutes}m{secs}s"

        # 使用 divmod 计算小时和分钟
        hours, minutes = divmod(minutes, 60)
        if hours < 24:
            return f"{hours}h{minutes}m"

        # 计算天数和小时
        days, hours = divmod(hours, 24)
        return f"{days}d{hours}h"

    def _format_relative_time(self, timestamp: float) -> str:
        """将时间戳格式化为相对时间字符串

        使用 datetime 模块计算时间差，逻辑更清晰。

        Args:
            timestamp: 时间戳

        Returns:
            str: 格式如 "刚刚", "5秒前", "3分钟前", "2小时前", "1天前"
        """
        from datetime import datetime

        now = datetime.now()
        past = datetime.fromtimestamp(timestamp)
        diff = now - past

        # 使用 total_seconds() 获取完整的时间差（包括天数转换的秒数）
        total_seconds = int(diff.total_seconds())

        if total_seconds < 5:
            return "刚刚"
        elif total_seconds < 60:
            return f"{total_seconds}秒前"
        elif total_seconds < 3600:
            # 使用 divmod 计算分钟
            minutes, _ = divmod(total_seconds, 60)
            return f"{minutes}分钟前"
        elif total_seconds < 86400:
            # 使用 divmod 计算小时
            hours, _ = divmod(total_seconds, 3600)
            return f"{hours}小时前"
        else:
            # 使用 divmod 计算天数
            days, _ = divmod(total_seconds, 86400)
            return f"{days}天前"

    # ========== 连接管理方法 ==========

    def get_connections_info(self) -> List[Dict]:
        """
        获取所有连接的信息

        Returns:
            List[Dict] 包含每个连接的详细信息
        """
        with self._lock:
            connections = []

            # 池中连接
            for conn in self._pool:
                connections.append(
                    {
                        "id": conn.id,
                        "status": "idle",
                        "created_at": conn.created_at,
                        "last_used": conn.last_used,
                        "use_count": conn.use_count,
                        "is_healthy": conn.is_healthy(),
                        "age_seconds": round(time.time() - conn.created_at, 1),
                        "idle_seconds": round(time.time() - conn.last_used, 1),
                    }
                )

            # 使用中的连接
            for conn in self._in_use:
                connections.append(
                    {
                        "id": conn.id,
                        "status": "in_use",
                        "created_at": conn.created_at,
                        "last_used": conn.last_used,
                        "use_count": conn.use_count,
                        "is_healthy": conn.is_healthy(),
                        "age_seconds": round(time.time() - conn.created_at, 1),
                        "idle_seconds": 0,
                    }
                )

            return connections

    def close_connection_by_id(self, connection_id: str) -> bool:
        """
        关闭指定 ID 的连接

        Args:
            connection_id: 连接 ID

        Returns:
            bool: 是否成功关闭
        """
        with self._lock:
            # 在池中查找
            for i, conn in enumerate(self._pool):
                if conn.id == connection_id:
                    conn.close()
                    self._pool.remove(conn)
                    self._stats_collector.record_connection_closed()
                    lifetime = time.time() - conn.created_at
                    self._stats_collector.record_connection_lifetime(lifetime)
                    logger.info(f"Closed connection {connection_id} from pool")
                    return True

            # 检查是否在使用中（不能关闭使用中的连接）
            for conn in self._in_use:
                if conn.id == connection_id:
                    logger.warning(f"Cannot close connection {connection_id}: currently in use")
                    return False

            logger.warning(f"Connection {connection_id} not found")
            return False

    def close_connections(self, count: int, strategy: str = "oldest") -> int:
        """
        关闭指定数量的连接

        Args:
            count: 要关闭的连接数
            strategy: 关闭策略 ("oldest", "newest", "least_used")

        Returns:
            int: 实际关闭的连接数
        """
        if count <= 0:
            return 0

        with self._lock:
            # 只能关闭池中的连接（空闲连接）
            available = len(self._pool)
            if available == 0:
                logger.warning("No idle connections available to close")
                return 0

            to_close = min(count, available)

            # 根据策略选择要关闭的连接
            if strategy == "oldest":
                # 按创建时间排序，关闭最老的
                candidates = sorted(self._pool, key=lambda c: c.created_at)[:to_close]
            elif strategy == "newest":
                # 按创建时间排序，关闭最新的
                candidates = sorted(self._pool, key=lambda c: c.created_at, reverse=True)[:to_close]
            elif strategy == "least_used":
                # 按使用次数排序，关闭使用最少的
                candidates = sorted(self._pool, key=lambda c: c.use_count)[:to_close]
            else:
                # 默认关闭最老的
                candidates = sorted(self._pool, key=lambda c: c.created_at)[:to_close]

            closed_count = 0
            for conn in candidates:
                conn.close()
                self._pool.remove(conn)
                self._stats_collector.record_connection_closed()
                lifetime = time.time() - conn.created_at
                self._stats_collector.record_connection_lifetime(lifetime)
                closed_count += 1

            logger.info(f"Closed {closed_count} connections using '{strategy}' strategy")
            return closed_count

    def close_idle_connections(self, min_idle_time: float) -> int:
        """
        关闭空闲时间超过指定值的连接

        Args:
            min_idle_time: 最小空闲时间（秒）

        Returns:
            int: 关闭的连接数
        """
        with self._lock:
            now = time.time()
            to_close = []

            for conn in list(self._pool):
                idle_time = now - conn.last_used
                if idle_time >= min_idle_time:
                    to_close.append(conn)

            closed_count = 0
            for conn in to_close:
                conn.close()
                self._pool.remove(conn)
                self._stats_collector.record_connection_closed()
                lifetime = now - conn.created_at
                self._stats_collector.record_connection_lifetime(lifetime)
                closed_count += 1

            if closed_count > 0:
                logger.info(
                    f"Closed {closed_count} idle connections " f"(idle >= {min_idle_time}s)"
                )
            return closed_count

    def close_connections_by_filter(self, filter_func: Callable[[PooledConnection], bool]) -> int:
        """
        根据自定义条件关闭连接

        Args:
            filter_func: 过滤函数，返回 True 表示要关闭该连接

        Returns:
            int: 关闭的连接数
        """
        with self._lock:
            to_close = [conn for conn in list(self._pool) if filter_func(conn)]

            closed_count = 0
            for conn in to_close:
                conn.close()
                self._pool.remove(conn)
                self._stats_collector.record_connection_closed()
                lifetime = time.time() - conn.created_at
                self._stats_collector.record_connection_lifetime(lifetime)
                closed_count += 1

            if closed_count > 0:
                logger.info(f"Closed {closed_count} connections by filter")
            return closed_count

    @property
    def stats(self) -> Dict:
        """获取连接池统计信息

        Returns:
            Dict 包含完整的连接池统计信息
        """
        if self._closed:
            return {
                **self._stats_collector.get_metrics().to_dict(),
                "pool_size": 0,
                "in_use": 0,
                "total": 0,
                "max_size": self._max_size,
                "closed": True,
            }

        with self._lock:
            return self._stats_collector.get_stats(
                current_pool_size=len(self._pool),
                current_in_use=len(self._in_use),
                max_size=self._max_size,
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PoolManager:
    """
    连接池管理器

    管理多个配置对应的连接池，负责创建、关闭和复用连接池。
    """

    def __init__(self):
        self._pools: Dict[str, ConnectionPool] = {}
        self._lock = threading.RLock()

    def _make_pool_key(self, config: SSHConfig) -> str:
        """生成连接池的唯一标识键"""
        return f"{config.username}@{config.host}:{config.port}"

    def create_pool(self, config: SSHConfig, **pool_kwargs) -> ConnectionPool:
        """
        创建新的连接池

        如果该配置的连接池已存在，则重置并复用现有连接池。

        Args:
            config: SSH配置
            **pool_kwargs: 连接池参数

        Returns:
            ConnectionPool: 连接池实例
        """
        pool_key = self._make_pool_key(config)

        with self._lock:
            if pool_key in self._pools:
                pool = self._pools[pool_key]
                # 如果连接池已关闭，重置它
                if pool._closed:
                    logger.info(f"Reusing and resetting existing pool for {pool_key}")
                    pool.reset()
                return pool
            else:
                # 创建新的连接池
                pool = ConnectionPool(config, **pool_kwargs)
                self._pools[pool_key] = pool
                logger.info(f"Created new pool for {pool_key}")
                return pool

    def get_or_create_pool(self, config: SSHConfig, **pool_kwargs) -> ConnectionPool:
        """
        获取或创建连接池

        如果连接池不存在或已关闭，会自动创建或重置。

        Args:
            config: SSH配置
            **pool_kwargs: 连接池参数

        Returns:
            ConnectionPool: 连接池
        """
        return self.create_pool(config, **pool_kwargs)

    def close_pool(self, config: SSHConfig) -> bool:
        """
        关闭指定配置对应的连接池

        关闭后连接池对象保留在管理器中，可以通过 create_pool 重新激活。

        Args:
            config: SSH配置

        Returns:
            bool: 是否成功关闭
        """
        pool_key = self._make_pool_key(config)

        with self._lock:
            if pool_key in self._pools:
                pool = self._pools[pool_key]
                try:
                    if not pool._closed:
                        pool.close()
                        logger.info(f"Closed pool for {pool_key}")
                    return True
                except Exception as e:
                    logger.error(f"Error closing pool {pool_key}: {e}")
                    return False
            return False

    def close_all(self, remove_pools: bool = False) -> None:
        """
        关闭所有连接池

        Args:
            remove_pools: 是否从管理器中移除连接池（默认保留以便复用）
        """
        with self._lock:
            for pool_key, pool in list(self._pools.items()):
                try:
                    if not pool._closed:
                        pool.close()
                        logger.info(f"Closed pool for {pool_key}")
                except Exception as e:
                    logger.error(f"Error closing pool {pool_key}: {e}")

            if remove_pools:
                self._pools.clear()

    def get_pool(self, config: SSHConfig) -> Optional[ConnectionPool]:
        """
        获取指定配置对应的连接池（如果不存在返回 None）

        Args:
            config: SSH配置

        Returns:
            Optional[ConnectionPool]: 连接池或 None
        """
        pool_key = self._make_pool_key(config)

        with self._lock:
            return self._pools.get(pool_key)

    def remove_pool(self, config: SSHConfig) -> bool:
        """
        从管理器中移除连接池（会先关闭连接）

        Args:
            config: SSH配置

        Returns:
            bool: 是否成功移除
        """
        pool_key = self._make_pool_key(config)

        with self._lock:
            if pool_key in self._pools:
                pool = self._pools.pop(pool_key)
                try:
                    if not pool._closed:
                        pool.close()
                except Exception as e:
                    logger.error(f"Error closing pool during removal {pool_key}: {e}")
                return True
            return False

    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有连接池统计信息"""
        with self._lock:
            return {key: pool.stats for key, pool in self._pools.items()}

    def list_pools(self) -> List[str]:
        """列出所有连接池的标识键"""
        with self._lock:
            return list(self._pools.keys())


# 全局连接池管理器
_global_pool_manager = PoolManager()


def get_pool_manager() -> PoolManager:
    """获取全局连接池管理器"""
    return _global_pool_manager
