# RemoteSSH 使用示例

包含15个使用示例，帮助快速上手。

## 快速开始

```bash
# 基本用法
python examples/basic_usage.py

# 连接池使用
python examples/pool_single_shell_example.py

# 多会话管理
python examples/multi_shell_session_demo.py
```

## 示例列表

### 基础示例
- **basic_usage.py** - SSHClient核心功能（命令执行、连接池、错误处理）
- **config_examples.py** - 配置加载（代码、YAML/JSON、环境变量）
- **monitoring.py** - 结构化日志和性能监控

### 连接池示例
- **pool_stats_demo.py** - 连接池统计展示
- **pool_reuse_demo.py** - 连接池关闭后复用和重置
- **pool_connection_management_demo.py** - 细粒度连接管理
- **pool_single_shell_example.py** - 传统连接池使用

### 架构示例
- **single_conn_multi_shell_example.py** - 单连接多Shell（资源受限场景）
- **multi_shell_session_demo.py** - 多会话管理
- **combined_architecture_example.py** - 组合架构（推荐）
- **architecture_comparison_demo.py** - 架构性能对比

### 高级示例
- **batch_operations.py** - 多服务器批量操作
- **advanced_patterns.py** - 高级用法（管道、文件操作、服务管理）

## 架构选择

| 场景 | 推荐方案 | 代码 |
|------|---------|------|
| 高并发批量操作 | 连接池+单Shell | `SSHClient(config, use_pool=True)` |
| 状态保持 | 单连接+多Shell | `MultiSessionManager(conn, config)` |
| 综合场景 | 连接池+多Shell | `pool.get_connection()` + `MultiSessionManager` |

## 配置方式

```python
# 1. 代码配置
config = SSHConfig(host="server.com", username="user", password="pass")

# 2. 文件配置
config = load_config(file_path="config.yaml")

# 3. 环境变量
export REMOTE_SSH_HOST="server.com"
config = load_config(use_env=True)
```

## 更多信息

- [架构对比](../docs/connection_architecture_comparison.md)
- [性能优化](../docs/performance_optimization.md)
- [项目状态](../PROJECT_STATUS.md)
