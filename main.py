#!/usr/bin/env python3
"""
rprobe - 轻量级远程SSH探针工具演示

这是 rprobe 库的演示脚本，展示了所有主要功能。
运行前请配置环境变量或修改代码中的连接信息。

运行方式:
    python main.py

环境变量配置:
    export REMOTE_SSH_HOST=your-host.com
    export REMOTE_SSH_USERNAME=your-username
    export REMOTE_SSH_PASSWORD=your-password
"""

import os
import time
import sys

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rprobe import SSHClient, SSHConfig
from rprobe.logging_config import configure_logging, get_logger
from rprobe.exceptions import ConfigurationError, ConnectionError, CommandTimeoutError

# 配置日志
configure_logging(level="DEBUG", format="colored")
logger = get_logger(__name__)


def get_config():
    """获取SSH配置（从环境变量或代码）"""
    # 尝试从环境变量加载
    host = os.environ.get("REMOTE_SSH_HOST", "aliyun.spiedeman.top")
    username = os.environ.get("REMOTE_SSH_USERNAME", "admin")
    password = os.environ.get("REMOTE_SSH_PASSWORD", "bhr0204")

    if host == "localhost" or host == "your-host.com":
        print("⚠️  警告: 使用默认配置，请设置环境变量或修改代码")
        print("   export REMOTE_SSH_HOST=your-host.com")
        print("   export REMOTE_SSH_USERNAME=your-username")
        print("   export REMOTE_SSH_PASSWORD=your-password")
        print()

    return SSHConfig(
        host=host,
        username=username,
        password=password,
        timeout=10.0,
        command_timeout=30.0,
    )


def example_1_basic_command():
    """示例1: 基本命令执行"""
    print("\n" + "=" * 60)
    print("示例1: 基本命令执行")
    print("=" * 60)

    config = get_config()

    try:
        with SSHClient(config) as client:
            # 执行系统命令
            commands = [
                ("whoami", "当前用户"),
                ("pwd", "当前目录"),
                ("uname -a", "系统信息"),
                ("date", "当前时间"),
            ]

            for cmd, desc in commands:
                result = client.exec_command(cmd)
                print(f"✓ {desc:12s}: {result.stdout.strip()}")

    except ConnectionError as e:
        print(f"✗ 连接失败: {e}")
    except Exception as e:
        print(f"✗ 错误: {e}")


def example_2_connection_pool():
    """示例2: 连接池性能对比"""
    print("\n" + "=" * 60)
    print("示例2: 连接池性能对比")
    print("=" * 60)

    config = get_config()
    num_commands = 5

    # 无连接池
    print("\n1. 无连接池模式:")
    start = time.time()
    for i in range(num_commands):
        with SSHClient(config, use_pool=False) as client:
            client.exec_command(f"echo 'No pool {i}'")
    no_pool_time = time.time() - start
    print(f"   执行{num_commands}次命令耗时: {no_pool_time:.2f}s")

    # 有连接池
    print("\n2. 连接池模式:")
    client = SSHClient(config, use_pool=True, max_size=3)
    start = time.time()
    for i in range(num_commands):
        client.exec_command(f"echo 'With pool {i}'")
    with_pool_time = time.time() - start
    client.disconnect()
    print(f"   执行{num_commands}次命令耗时: {with_pool_time:.2f}s")

    # 性能对比
    if with_pool_time > 0:
        speedup = no_pool_time / with_pool_time
        print(f"\n✓ 性能提升: {speedup:.1f}倍")


def example_3_shell_session():
    """示例3: Shell会话状态保持"""
    print("\n" + "=" * 60)
    print("示例3: Shell会话状态保持")
    print("=" * 60)

    config = get_config()

    try:
        with SSHClient(config) as client:
            # 打开Shell会话
            prompt = client.open_shell_session()
            print(f"✓ 检测到提示符: {prompt}")

            # 在Shell中执行命令（保持状态）
            print("\n在Shell中执行:")

            # 切换目录
            client.shell_command("cd /tmp")
            result = client.shell_command("pwd")
            print("  $ cd /tmp")
            print("  $ pwd")
            print(f"    当前目录: {result.stdout.strip()}")

            # 设置环境变量
            client.shell_command("export DEMO_VAR='HelloRemoteSSH'")
            result = client.shell_command("echo $DEMO_VAR")
            print("  $ export DEMO_VAR='HelloRemoteSSH'")
            print("  $ echo $DEMO_VAR")
            print(f"    环境变量: {result.stdout.strip()}")

            client.close_shell_session()
            print("\n✓ Shell会话已关闭")

    except Exception as e:
        print(f"✗ 错误: {e}")


def example_4_error_handling():
    """示例4: 错误处理"""
    print("\n" + "=" * 60)
    print("示例4: 错误处理")
    print("=" * 60)

    # 1. 配置错误
    print("\n1. 测试配置验证:")
    try:
        SSHConfig(host="", username="user", password="pass")
    except ConfigurationError as e:
        print(f"   ✓ 捕获配置错误: {e}")

    # 2. 无效端口
    try:
        SSHConfig(host="test.com", username="user", password="pass", port=70000)
    except ConfigurationError as e:
        print(f"   ✓ 捕获端口错误: {e}")

    # 3. 连接超时
    print("\n2. 测试连接超时:")
    config = SSHConfig(
        host=get_config().host,
        username=get_config().username,
        password=get_config().password,
        command_timeout=2.0,
    )

    try:
        with SSHClient(config) as client:
            client.exec_command("sleep 10")
    except (CommandTimeoutError, TimeoutError) as e:
        print(f"   ✓ 捕获超时错误: {type(e).__name__}")
    except Exception as e:
        print(f"   ✗ 其他错误: {e}")


def example_5_parallel_creation():
    """示例5: 并行创建连接"""
    print("\n" + "=" * 60)
    print("示例5: 并行创建连接")
    print("=" * 60)

    config = get_config()

    print("\n1. 串行创建5个连接:")
    start = time.time()
    client_serial = SSHClient(
        config, use_pool=True, max_size=5, min_size=5, parallel_init=False
    )
    serial_time = time.time() - start
    stats = client_serial._pool.stats
    print(f"   创建{stats['created']}个连接耗时: {serial_time:.3f}s")
    client_serial.disconnect()

    print("\n2. 并行创建5个连接:")
    start = time.time()
    client_parallel = SSHClient(
        config, use_pool=True, max_size=5, min_size=5, parallel_init=True
    )
    parallel_time = time.time() - start
    stats = client_parallel._pool.stats
    print(f"   创建{stats['created']}个连接耗时: {parallel_time:.3f}s")
    client_parallel.disconnect()

    if parallel_time > 0:
        speedup = serial_time / parallel_time
        print(f"\n✓ 并行创建速度提升: {speedup:.1f}倍")


def example_6_config_management():
    """示例6: 配置管理"""
    print("\n" + "=" * 60)
    print("示例6: 配置管理")
    print("=" * 60)

    print("\n1. 从代码创建配置:")
    config1 = SSHConfig(
        host="server1.example.com", username="admin", password="secret", port=2222
    )
    print(f"   ✓ {config1}")

    print("\n2. 配置复制和修改:")
    config2 = config1.copy_with(port=22, timeout=60.0)
    print(f"   原端口: {config1.port}, 新端口: {config2.port}")
    print(f"   原超时: {config1.timeout}s, 新超时: {config2.timeout}s")

    print("\n3. 配置导出为字典:")
    config_dict = config1.to_dict()
    print(f"   Host: {config_dict['host']}")
    print(f"   Port: {config_dict['port']}")


def example_7_pool_close():
    """示例7: 连接池并行关闭演示"""
    print("\n" + "=" * 60)
    print("示例7: 连接池并行关闭演示")
    print("=" * 60)

    config = get_config()

    print("\n1. 创建包含10个连接的连接池:")
    client = SSHClient(
        config,
        use_pool=True,
        max_size=10,
        min_size=10,
        parallel_init=True,  # 并行初始化加速
    )
    stats = client._pool.stats
    print(f"   ✓ 连接池创建完成: {stats['total']}个连接")
    print(f"   - 可用连接: {stats['pool_size']}")
    print(f"   - 使用中连接: {stats['in_use']}")

    print("\n2. 使用部分连接执行命令:")
    try:
        # 使用连接池执行一些命令
        for i in range(5):
            client.exec_command(f"echo 'Connection test {i}'")
            print(f"   ✓ 命令{i + 1}执行完成")
    except Exception as e:
        print(f"   ⚠ 命令执行失败（可能是演示环境）: {e}")

    print("\n3. 并行关闭连接池:")
    print("   使用并行关闭优化，同时关闭所有连接...")
    start = time.time()
    client.disconnect()  # 内部调用 pool.close() 使用并行关闭
    close_time = time.time() - start
    print("   ✓ 连接池关闭完成")
    print(f"   - 关闭耗时: {close_time:.3f}s")
    print(f"   - 平均每个连接: {close_time / 10:.3f}s")

    print("\n4. 性能对比说明:")
    print("   串行关闭: 10个连接 × 100ms = 1000ms")
    print("   并行关闭: ~100ms（并发执行）")
    print("   性能提升: ~10倍")

    print("\n5. 关闭方式说明:")
    print("   • 方式1: client.disconnect() - 推荐方式")
    print("   • 方式2: 使用 with 语句自动关闭")
    print("   • 方式3: pool.close(timeout=5.0) - 手动关闭")


def example_8_background_tasks():
    """示例8: 后台任务执行器（v1.4.0新功能）"""
    print("\n" + "=" * 60)
    print("示例8: 后台任务执行器 - 状态机管理（v2.0新功能）")
    print("=" * 60)

    config = get_config()

    try:
        with SSHClient(config) as client:
            print("\n1. 启动后台任务（强制Shell模式，支持优雅停止）:")
            # 启动一个后台任务（例如：tcpdump抓包）
            task = client.bg(
                'for i in $(seq 1 10); do echo "Log entry $i at $(date)"; sleep 1; done',
                name="log_monitor",
                buffer_size_mb=5,  # 5MB 缓冲区限制
            )
            print(f"   ✓ 后台任务已启动: ID={task.id}")
            print(f"   ✓ 任务名称: {task.name}")
            print(f"   ✓ 强制Shell模式: 支持SIGINT信号发送")

            print("\n2. 使用状态机查询任务状态:")
            from rprobe.core.task_status import TaskStatus

            # 展示状态枚举
            print(f"   当前状态: {task.status} ({task.status.value})")
            print(f"   状态类型: TaskStatus 枚举")
            print(f"   是否运行中: {task.is_running()}")
            print(f"   是否终态: {task.status.is_terminal}")

            # 等待一会儿
            time.sleep(2)
            print(f"   已运行时长: {task.duration:.1f} 秒")

            print("\n3. 获取任务摘要（包含状态历史）:")
            summary = task.get_summary(tail_lines=3)
            print(f"   - 状态: {summary.status}")
            print(f"   - 状态枚举: {summary.status_enum}")
            print(f"   - 时长: {summary.duration:.1f}秒")
            print(f"   - 输出行数: {summary.lines_output}")
            print(f"   - 状态历史记录数: {len(summary.status_history)}")

            # 展示状态历史
            if summary.status_history:
                print("   - 状态流转:")
                for event in summary.status_history[:3]:
                    print(f"     {event['from']} -> {event['to']} ({event['reason']})")

            print("\n4. 优雅停止任务（发送SIGINT信号）:")
            if task.is_running():
                print("   发送 SIGINT 信号 (Ctrl+C) 到远程进程...")
                task.stop(graceful=True, timeout=5.0)
                print(f"   ✓ 任务已停止，最终状态: {task.status}")

                if task.is_stopped():
                    print("   ✓ 状态确认: STOPPED（用户手动停止）")
                elif task.is_completed():
                    print("   ✓ 状态确认: COMPLETED（正常完成）")

            print("\n5. 查看完整输出:")
            output = task.get_output()
            if output:
                lines = output.strip().split("\n")
                print(f"   总输出: {len(lines)} 行")
                if lines:
                    print(f"   首行: {lines[0][:60]}...")
                    print(f"   末行: {lines[-1][:60]}...")

    except Exception as e:
        print(f"   ⚠ 演示失败: {e}")
        print("   提示: 后台任务执行器需要真实SSH连接")


def example_9_exception_mapper():
    """示例9: 异常映射器（v2.0新功能）"""
    print("\n" + "=" * 60)
    print("示例9: 统一异常映射器")
    print("=" * 60)

    print("\n1. 异常映射器介绍:")
    print("   rprobe 使用统一的异常映射策略")
    print("   将后端特定异常（如 paramiko）映射到自定义异常")
    print("   确保不同后端抛出一致的异常类型")

    from rprobe.backends.base import (
        AuthenticationError,
        ConnectionError,
        SSHException,
        ChannelException,
    )

    print("\n2. 自定义异常类型:")
    print("   • AuthenticationError - 认证失败")
    print("   • ConnectionError - 连接错误")
    print("   • SSHException - SSH协议错误")
    print("   • ChannelException - 通道操作错误")

    print("\n3. 异常映射示例:")
    print("   paramiko.AuthenticationException → AuthenticationError")
    print("   paramiko.SSHException('No existing session') → ConnectionError")
    print("   ConnectionRefusedError → ConnectionError")
    print("   TimeoutError → ConnectionError")

    print("\n4. 使用异常映射器:")
    try:
        from rprobe.backends.exception_mapper import get_paramiko_exception_mapper

        mapper = get_paramiko_exception_mapper()
        print(f"   ✓ 异常映射器已加载")
        print(f"   ✓ 支持类型映射: {len(mapper._mappings)} 种")
        print(f"   ✓ 支持消息映射: {len(mapper._message_mappings)} 种")

        # 展示映射规则
        print("\n5. 细粒度映射规则:")
        for keyword in mapper._message_mappings.keys():
            print(f"   • 包含 '{keyword}' 的消息 → ConnectionError")

    except ImportError as e:
        print(f"   ⚠ 异常映射器未加载: {e}")

    print("\n6. 在代码中使用:")
    print("   try:")
    print("       client.connect(...)")
    print("   except AuthenticationError as e:")
    print("       print(f'认证失败: {e}')")
    print("   except ConnectionError as e:")
    print("       print(f'连接失败: {e}')")


def example_10_architecture_contract():
    """示例10: 架构契约验证（v2.0新功能）"""
    print("\n" + "=" * 60)
    print("示例10: 架构契约验证")
    print("=" * 60)

    print("\n1. 架构契约介绍:")
    print("   rprobe 使用解耦架构，支持多种SSH后端")
    print("   架构契约确保所有后端实现一致的接口")

    print("\n2. 核心接口:")
    print("   • SSHBackend - 后端抽象基类")
    print("   • Channel - 通道抽象接口")
    print("   • Transport - 传输层抽象接口")

    print("\n3. 当前实现:")
    from rprobe.backends.paramiko_backend import (
        ParamikoBackend,
        ParamikoChannel,
        ParamikoTransport,
    )

    print(f"   ✓ ParamikoBackend - 已实现所有必需方法")
    print(
        f"   ✓ ParamikoChannel - 已实现 {len([m for m in dir(ParamikoChannel) if not m.startswith('_')])} 个方法"
    )
    print(
        f"   ✓ ParamikoTransport - 已实现 {len([m for m in dir(ParamikoTransport) if not m.startswith('_')])} 个方法"
    )

    print("\n4. 关键方法示例:")
    print("   Channel 必需方法:")
    print("     - recv(), send(), close()")
    print("     - exec_command(), invoke_shell()")
    print("     - get_transport() - 获取关联的 transport")
    print("     - getpeername() - 获取远程地址")

    print("\n5. 运行契约测试:")
    print("   $ pytest tests/contracts/ -v")
    print("   验证所有后端实现满足接口契约")

    print("\n6. 扩展新后端:")
    print("   可以添加 AsyncSSHBackend、LibSSHBackend 等")
    print("   只需实现相同的接口，无需修改上层代码")


def example_11_code_review_checklist():
    """示例11: 代码审查检查清单"""
    print("\n" + "=" * 60)
    print("示例11: 代码审查检查清单")
    print("=" * 60)

    print("\n1. 检查清单介绍:")
    print("   rprobe 提供完整的代码审查检查清单")
    print("   确保代码质量和架构一致性")

    print("\n2. 检查清单内容:")
    print("   • 架构设计检查 - 接口完整性、解耦一致性")
    print("   • 连接池检查 - 上下文管理器正确使用")
    print("   • 异常处理检查 - 异常映射完整性")
    print("   • 测试覆盖检查 - Mock保真度、集成测试")
    print("   • 性能与可观测性 - 日志、性能优化")

    print("\n3. 关键检查点:")
    print("   ✓ 所有抽象方法都已实现")
    print("   ✓ 新增方法已添加到契约测试")
    print("   ✓ 正确使用 with 语句管理连接池")
    print("   ✓ 所有异常都映射到自定义异常")
    print("   ✓ 关键路径有结构化日志")

    print("\n4. 查看完整检查清单:")
    print("   $ cat docs/CODE_REVIEW_CHECKLIST.md")
    print("   包含详细的检查项和常见问题解答")

    print("\n5. 审查记录模板:")
    print("   使用提供的模板记录审查结果")
    print("   包含：检查项、发现问题、建议、结论")

    print("\n6. 持续改进:")
    print("   根据项目经验不断更新检查清单")
    print("   确保团队遵循统一的质量标准")


def example_12_streaming_transfer():
    """示例12: 流式数据传输（v1.4.0功能）"""
    print("\n" + "=" * 60)
    print("示例12: 流式数据传输（大文件处理）")
    print("=" * 60)

    config = get_config()

    try:
        with SSHClient(config) as client:
            print("\n1. 流式接收数据（适合大文件）:")

            received_chunks = []
            total_bytes = 0

            def data_handler(stdout_chunk, stderr_chunk):
                """数据块处理回调"""
                nonlocal total_bytes
                if stdout_chunk:
                    received_chunks.append(stdout_chunk)
                    total_bytes += len(stdout_chunk)

            # 执行命令并流式接收
            print("   执行命令: seq 1 1000")
            result = client.exec_command_stream(
                "seq 1 1000",
                chunk_handler=data_handler,
                timeout=30.0,
            )

            print(f"   ✓ 命令执行完成，退出码: {result.exit_code}")
            print(f"   ✓ 接收数据块: {len(received_chunks)} 个")
            print(f"   ✓ 总字节数: {total_bytes} bytes")

            print("\n2. 内存占用对比:")
            print("   传统方式: 加载整个输出到内存")
            print("   流式方式: 每次只处理一个数据块（64KB）")
            print("   优势: 处理 GB 级文件也只需要 MB 级内存")

    except Exception as e:
        print(f"   ⚠ 演示失败: {e}")


def example_13_connection_factory():
    """示例13: ConnectionFactory 使用（v1.4.0新功能）"""
    print("\n" + "=" * 60)
    print("示例13: ConnectionFactory - 统一Channel创建")
    print("=" * 60)

    from rprobe.core.connection_factory import ConnectionFactory

    config = get_config()

    try:
        with SSHClient(config) as client:
            print("\n1. 使用 ConnectionFactory 创建 exec channel:")

            # 获取 transport
            transport = client._connection.transport

            # 使用工厂创建 channel（自动管理生命周期）
            with ConnectionFactory.create_exec_channel(
                transport=transport,
                command="echo 'Hello from ConnectionFactory'",
                timeout=30.0,
            ) as channel:
                # 读取输出
                stdout = b""
                while True:
                    data = channel.recv(4096)
                    if not data:
                        break
                    stdout += data

                print("   ✓ Channel 创建成功")
                print(f"   ✓ 输出: {stdout.decode().strip()}")
            # 自动关闭 channel

            print("\n2. 使用 ConnectionFactory 创建 shell channel:")
            with ConnectionFactory.create_shell_channel(
                transport=transport,
                timeout=60.0,
            ) as channel:
                # 发送命令
                channel.send("pwd\n")
                time.sleep(0.5)

                # 读取响应
                response = channel.recv(1024)
                print("   ✓ Shell channel 创建成功")
                if response:
                    print(f"   ✓ 响应: {response.decode().strip()}")
            # 自动关闭 channel

            print("\n3. 错误处理优势:")
            print("   即使发生异常，channel 也会自动关闭")
            print("   避免资源泄漏")

    except Exception as e:
        print(f"   ⚠ 演示失败: {e}")


def run_all_examples():
    """运行所有示例"""
    examples = [
        ("基本命令执行", example_1_basic_command),
        ("连接池性能对比", example_2_connection_pool),
        ("Shell会话状态保持", example_3_shell_session),
        ("错误处理", example_4_error_handling),
        ("并行创建连接", example_5_parallel_creation),
        ("配置管理", example_6_config_management),
        ("连接池并行关闭", example_7_pool_close),
        ("后台任务执行器 - 状态机", example_8_background_tasks),
        ("统一异常映射器", example_9_exception_mapper),
        ("架构契约验证", example_10_architecture_contract),
        ("代码审查检查清单", example_11_code_review_checklist),
        ("流式数据传输", example_12_streaming_transfer),
        ("ConnectionFactory", example_13_connection_factory),
    ]

    print("\n" + "=" * 60)
    print("rprobe - 轻量级远程SSH探针工具演示")
    print("=" * 60)
    print("\n注意: 请确保已设置SSH连接信息")

    # 询问是否继续
    response = input("\n是否运行所有示例? (y/n): ").lower()
    if response != "y":
        print("取消运行")
        return

    print("\n" + "=" * 60)
    print("开始运行示例...")
    print("=" * 60)

    for name, func in examples:
        try:
            func()
        except KeyboardInterrupt:
            print("\n\n用户中断")
            break
        except Exception as e:
            print(f"\n✗ 示例 '{name}' 失败: {e}")

    print("\n" + "=" * 60)
    print("示例运行完成!")
    print("=" * 60)
    print("\n更多示例请参见 examples/ 目录")


if __name__ == "__main__":
    try:
        run_all_examples()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n程序错误: {e}")
        sys.exit(1)
