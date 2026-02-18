# RemoteSSH - 高性能 Python SSH 客户端

[![Tests](https://img.shields.io/badge/tests-700%2B%20passing-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)]()

一个功能完善的 Python SSH 客户端库，提供连接池管理、结构化日志、多源配置等高级功能。

## 核心特性

- **连接池管理** - 连接复用、健康检查、并行创建/关闭
- **单连接多会话** - 单个SSH连接支持多个独立Shell会话
- **流式数据处理** - 超大数据传输支持，低内存占用
- **结构化日志** - JSON格式、上下文绑定
- **多源配置** - 代码、YAML/JSON、环境变量
- **性能优化** - 自适应轮询、多种数据接收模式
- **测试优化** - 集成测试时间缩短70%（401秒→120秒）

## 快速开始

```python
from src import SSHClient, SSHConfig

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
```

## 安装

```bash
# 克隆仓库
git clone <repository-url>
cd RemoteSSH

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

- **单元测试**: 618个（100%通过）
- **集成测试**: 145个（100%通过）
- **代码覆盖率**: 92%
- **单元测试执行时间**: ~3.7秒
- **集成测试执行时间**: ~120秒（优化后，原401秒）

## 文档

- [开发指南](AGENTS.md) - 开发环境设置和工作流程
- [项目状态](PROJECT_STATUS.md) - 详细功能说明和测试报告
- [架构对比](docs/connection_architecture_comparison.md) - 连接池 vs 单连接+多Shell
- [性能优化](docs/performance_optimization.md) - 性能调优指南
- [流式API](examples/streaming_api_example.py) - 流式数据传输示例
- [测试优化](docs/optimization_implementation_report.md) - 集成测试优化报告
- [变更日志](CHANGELOG.md) - 版本变更记录

## 许可证

MIT License
