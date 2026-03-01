# rprobe - 轻量级远程 SSH 探针工具

[![Tests](https://img.shields.io/badge/tests-700%2B%20passing-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)]()

一个轻量级的 SSH 探针工具，用于快速手动测试和远程设备探查。支持多会话管理、结构化输出和 DSL 模式提取。

## 核心特性

- **后台任务执行** - 非阻塞执行长时间命令（如tcpdump），支持实时输出和任务管理
- **批量后台任务** - 并发控制、批量启动/停止/监控多个后台任务
- **连接池管理** - 连接复用、健康检查、并行创建/关闭
- **单连接多会话** - 单个SSH连接支持多个独立Shell会话
- **流式数据处理** - 超大数据传输支持，低内存占用
- **ConnectionFactory** - 统一封装Channel创建，消除重复代码，自动资源管理
- **结构化日志** - JSON格式、上下文绑定
- **多源配置** - 代码、YAML/JSON、环境变量
- **性能优化** - 自适应轮询、多种数据接收模式
- **测试优化** - 集成测试时间缩短70%（401秒→120秒）

## 快速开始

```python
from rprobe import SSHClient, SSHConfig

# 创建配置
config = SSHConfig(
    host="example.com",
    username="admin",
    password="secret"
)

# 使用连接池执行命令
with SSHClient(config, use_pool=True) as client:
    result = client.exec_command("ls -la")
    print(result.stdout)

# 流式处理超大数据（1MB+，低内存占用）
total_size = 0
def handle_chunk(stdout, stderr):
    global total_size
    if stdout:
        total_size += len(stdout)
        # 实时处理数据块，不缓存完整输出

with SSHClient(config) as client:
    result = client.exec_command_stream(
        "cat large_file",
        handle_chunk,
        timeout=60.0
    )
    print(f"传输完成，共接收 {total_size} 字节")

# 后台执行长时间任务（如tcpdump）
with SSHClient(config) as client:
    # 启动后台抓包任务
    task = client.bg(
        "tcpdump -i eth0 port 80 -c 1000 -w /tmp/http.pcap",
        name="http_capture"
    )
    
    # 主线程继续执行其他工作
    print(f"任务运行中: {task.id}")
    time.sleep(30)
    
    # 检查状态并获取摘要
    summary = task.get_summary()
    print(f"任务状态: {summary.status}")
    print(f"远程文件: {summary.remote_files}")
    
    # 停止任务
    task.stop(graceful=True)

# 批量后台任务 - 并发控制、批量管理
with SSHClient(config, use_pool=False) as client:
    # 准备批量任务
    commands = [
        {"command": "tcpdump -i eth0 -w /tmp/cap1.pcap", "name": "capture_eth0"},
        {"command": "tcpdump -i eth1 -w /tmp/cap2.pcap", "name": "capture_eth1"},
        {"command": "tail -f /var/log/nginx/access.log", "name": "nginx_log"},
        {"command": "tail -f /var/log/app/error.log", "name": "app_log"},
    ]
    
    # 批量启动（最多2个并发，间隔0.5秒）
    batch = client._bg_manager.run_batch(
        commands,
        max_concurrent=2,
        batch_delay=0.5
    )
    
    print(f"已启动 {len(batch.tasks)} 个任务")
    print(f"运行中: {batch.running_count}")
    
    # 等待所有任务完成（最多5分钟）
    if batch.wait_all(timeout=300):
        print("✅ 所有任务完成")
    else:
        print("⚠️  等待超时")
    
    # 获取所有结果
    for summary in batch.get_summaries():
        print(f"{summary.name}: {summary.status} ({summary.duration:.1f}s)")
    
    # 或者批量停止
    # batch.stop_all(graceful=True)

# ConnectionFactory - 统一Channel创建
from rprobe.core.connection_factory import ConnectionFactory

with SSHClient(config) as client:
    transport = client._connection.transport
    
    # 使用工厂创建exec channel（自动关闭）
    with ConnectionFactory.create_exec_channel(
        transport=transport,
        command="ls -la",
        timeout=30.0
    ) as channel:
        stdout = channel.recv(1024)
        print(stdout.decode())
    # channel自动关闭
```

## 安装

```bash
# 克隆仓库
git clone <repository-url>
cd rprobe

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -e .

# 运行测试
TESTING=true python -m pytest tests/unit -v
```

## 架构支持

支持三种架构模式：

| 模式 | 适用场景 | 特点 |
|------|---------|------|
| **连接池+单Shell** | 高并发批量操作 | 真正并行，资源消耗大 |
| **单连接+多Shell** | 状态保持、资源受限 | 状态隔离，资源节省 |
| **连接池+多Shell** | 综合场景（推荐）| 并行+状态隔离最佳平衡 |

## 项目统计

- **单元测试**: 812个（96.8%通过）
- **集成测试**: 145个（100%通过）
- **代码覆盖率**: ~70%
- **单元测试执行时间**: ~12秒
- **集成测试执行时间**: ~120秒（优化后，原401秒）

## 文档

- [开发指南](AGENTS.md) - 开发环境设置和工作流程
- [项目状态](PROJECT_STATUS.md) - 详细功能说明和测试报告
- [架构对比](docs/connection_architecture_comparison.md) - 连接池 vs 单连接+多Shell
- [后台任务指南](docs/ASYNC_EXECUTOR_GUIDE.md) - 后台任务执行说明
- [ConnectionFactory](docs/CONNECTION_FACTORY_IMPLEMENTATION.md) - Channel创建工厂说明
- [性能优化](docs/performance_optimization.md) - 性能调优指南
- [流式API](examples/streaming_api_example.py) - 流式数据传输示例
- [后台任务示例](examples/async_executor_example.py) - 后台任务使用示例
- [ConnectionFactory示例](examples/connection_factory_example.py) - Channel工厂使用示例
- [变更日志](CHANGELOG.md) - 版本变更记录

## 许可证

MIT License
