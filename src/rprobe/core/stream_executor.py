"""
流式命令执行模块

提供流式命令执行功能，支持超大数据传输和低内存占用。
通过回调函数实时处理数据块，避免累积完整输出。

此模块属于业务逻辑层，协调以下组件：
- ConnectionPool/ConnectionManager: 提供连接
- SmartChannelReceiver: 流式数据接收
- SSHConfig: 配置参数

Example:
    executor = StreamExecutor(client)

    def handle_chunk(stdout, stderr):
        process_data(stdout)

    result = executor.execute(
        "cat large_file",
        handle_chunk,
        timeout=60.0
    )
"""

import logging
import time
from typing import Callable, Optional, TYPE_CHECKING

from rprobe.config.models import SSHConfig
from rprobe.core.models import CommandResult
from rprobe.core.connection_factory import ConnectionFactory
from rprobe.receivers.smart_receiver import SmartChannelReceiver, create_receiver

if TYPE_CHECKING:
    from rprobe.core.client import SSHClient


logger = logging.getLogger(__name__)


class StreamExecutor:
    """
    流式命令执行器

    负责执行需要流式处理的命令，支持：
    - 超大数据传输（1MB+，O(1)内存占用）
    - 实时数据处理和回调
    - 连接池和直接连接两种模式
    - 完整的超时和错误处理

    Attributes:
        _client: SSHClient 实例，用于获取连接
        _config: SSH 配置
        _receiver: 智能通道接收器
    """

    def __init__(self, client: "SSHClient"):
        """
        初始化流式执行器

        Args:
            client: SSHClient 实例，用于获取连接和配置
        """
        self._client = client
        self._config = client._config
        self._receiver = create_receiver(self._config)

        logger.debug(f"StreamExecutor 初始化完成，模式: {self._receiver.mode}")

    def execute(
        self,
        command: str,
        chunk_handler: Callable[[bytes, bytes], None],
        timeout: Optional[float] = None,
    ) -> CommandResult:
        """
        流式执行命令

        执行命令并通过回调函数实时处理输出的数据块。
        适用于超大数据传输场景，内存占用极低。

        Args:
            command: 要执行的命令
            chunk_handler: 回调函数，接收 (stdout_chunk, stderr_chunk)
                          每次收到数据块时立即调用
            timeout: 命令执行超时（秒），默认使用配置中的 command_timeout

        Returns:
            CommandResult: 命令执行结果
                          - stdout/stderr 为空字符串（数据已通过回调处理）
                          - exit_code: 命令退出码
                          - execution_time: 执行耗时
                          - command: 执行的命令

        Raises:
            TimeoutError: 命令执行超时
            ConnectionError: SSH 连接断开
            RuntimeError: 其他执行错误

        Example:
            total_size = 0

            def handle_chunk(stdout, stderr):
                nonlocal total_size
                if stdout:
                    total_size += len(stdout)
                    print(f"收到 {len(stdout)} 字节")

            result = executor.execute(
                "cat /var/log/large.log",
                handle_chunk,
                timeout=60.0
            )
            print(f"总共接收: {total_size} 字节，退出码: {result.exit_code}")
        """
        cmd_timeout = timeout or self._config.command_timeout
        start_time = time.time()

        logger.info(f"[StreamExecutor] 开始流式执行命令: {command}")

        # 根据客户端配置选择执行策略
        if self._client._use_pool:
            return self._execute_with_pool(command, chunk_handler, cmd_timeout, start_time)
        else:
            return self._execute_direct(command, chunk_handler, cmd_timeout, start_time)

    def _execute_with_pool(
        self,
        command: str,
        chunk_handler: Callable[[bytes, bytes], None],
        cmd_timeout: float,
        start_time: float,
    ) -> CommandResult:
        """
        使用连接池流式执行命令

        Args:
            command: 要执行的命令
            chunk_handler: 数据块回调函数
            cmd_timeout: 命令超时时间
            start_time: 开始时间戳

        Returns:
            CommandResult: 命令执行结果
        """
        # 使用 ConnectionFactory 管理 channel 生命周期
        with ConnectionFactory.create_exec_channel(
            connection_source=self._client._pool,
            use_pool=True,
            command=command,
            timeout=cmd_timeout,
        ) as channel:
            transport = channel.get_transport()

            # 使用接收器流式获取数据
            exit_code = self._receiver.recv_stream(
                channel, chunk_handler, timeout=cmd_timeout, transport=transport
            )

            execution_time = time.time() - start_time

            logger.info(
                f"[StreamExecutor] 流式命令执行完成: exit_code={exit_code}, "
                f"耗时={execution_time:.3f}秒"
            )

            # 返回空字符串作为 stdout/stderr，因为数据已通过回调处理
            return CommandResult(
                stdout="",
                stderr="",
                exit_code=exit_code,
                execution_time=execution_time,
                command=command,
            )

    def _execute_direct(
        self,
        command: str,
        chunk_handler: Callable[[bytes, bytes], None],
        cmd_timeout: float,
        start_time: float,
    ) -> CommandResult:
        """
        直接流式执行命令（不使用连接池）

        Args:
            command: 要执行的命令
            chunk_handler: 数据块回调函数
            cmd_timeout: 命令超时时间
            start_time: 开始时间戳

        Returns:
            CommandResult: 命令执行结果

        Raises:
            TimeoutError: 命令执行超时
            ConnectionError: SSH 连接断开
            RuntimeError: 其他执行错误
        """
        try:
            # 使用 ConnectionFactory 管理 channel 生命周期
            # ConnectionFactory 内部会调用 ensure_connected
            with ConnectionFactory.create_exec_channel(
                connection_source=self._client._connection,
                use_pool=False,
                command=command,
                timeout=cmd_timeout,
            ) as channel:
                transport = channel.get_transport()

                # 使用接收器流式获取数据
                exit_code = self._receiver.recv_stream(
                    channel, chunk_handler, timeout=cmd_timeout, transport=transport
                )

                execution_time = time.time() - start_time

                logger.info(
                    f"[StreamExecutor] 流式命令执行完成: exit_code={exit_code}, "
                    f"耗时={execution_time:.3f}秒"
                )

                return CommandResult(
                    stdout="",
                    stderr="",
                    exit_code=exit_code,
                    execution_time=execution_time,
                    command=command,
                )
        except TimeoutError:
            raise
        except ConnectionError:
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"[StreamExecutor] 流式命令执行异常 ({execution_time:.3f}秒): " f"{command} - {e}"
            )
            raise RuntimeError(f"流式命令执行失败: {e}") from e
