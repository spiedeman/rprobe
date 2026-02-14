# 后台任务执行模块 - 使用指南

## 🎉 功能概述

已完成后台任务执行模块的实现，支持tcpdump等长时间命令的非阻塞执行。

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| **字节限制缓冲区** | 默认10MB环形缓冲区，防止内存溢出 |
| **自动清理** | 任务完成1小时后自动从管理器移除 |
| **名称管理** | 支持通过名称管理任务，重复名称报错 |
| **优雅停止** | 支持SIGINT优雅停止和强制关闭 |
| **自动日志** | 任务完成自动记录日志，无需回调 |

## 🚀 快速开始

### 安装

确保已安装RemoteSSH库：
```bash
pip install -e .
```

### 基本使用

```python
from src import SSHClient, SSHConfig

# 创建客户端
config = SSHConfig(host="your-server.com", username="root", password="your-password")
client = SSHClient(config)
client.connect()

# 启动后台任务
task = client.bg(
    "tcpdump -i eth0 port 80 -c 1000 -w /tmp/http.pcap",
    name="http_capture"
)

# 主线程做其他事
import time
time.sleep(30)

# 检查状态
if task.is_running():
    print(f"运行中，已运行 {task.duration:.1f} 秒")

# 停止任务
task.stop(graceful=True, timeout=5.0)

# 获取摘要（轻量级，不下载文件）
summary = task.get_summary()
print(summary)
# 输出：
# [✓] [a3f7b2d] tcpdump -i eth0 port 80 -c 1000...
#     状态: completed | 退出码: 0
#     时长: 45.2s | 输出: 0行/0B
#     远程文件: /tmp/http.pcap

client.disconnect()
```

## 📚 API参考

### SSHClient.bg()

```python
def bg(
    self,
    command: str,
    name: Optional[str] = None,
    buffer_size_mb: float = 10.0,
    cleanup_delay: float = 3600.0
) -> BackgroundTask
```

**参数说明：**
- `command`: 要执行的命令
- `name`: 可选的任务名称（用于后续查找）
- `buffer_size_mb`: 环形缓冲区大小（MB），默认10MB
- `cleanup_delay`: 自动清理延迟（秒），默认1小时

**返回值：**
- `BackgroundTask`: 任务对象

### BackgroundTask对象

**状态查询：**
```python
task.is_running()      # 是否在运行中
task.is_completed()    # 是否自己完成
task.is_stopped()      # 是否被停止
task.duration          # 运行时长（秒）
task.status            # 当前状态字符串
```

**控制方法：**
```python
task.stop(graceful=True, timeout=5.0)  # 停止任务
task.wait(timeout=None)                 # 等待完成
```

**获取结果：**
```python
task.get_summary()      # 获取轻量级摘要
task.get_output()       # 获取stdout输出
task.get_stderr()       # 获取stderr输出
task.get_result()       # 获取完整结果
```

### 任务管理器

```python
# 获取所有任务
all_tasks = client.background_tasks

# 通过ID获取任务
task = client.get_background_task("a3f7b2d")

# 通过名称获取任务
task = client.get_background_task_by_name("http_capture")

# 批量停止所有任务
client.stop_all_background(graceful=True, timeout=5.0)
```

## 📖 完整示例

参见 `examples/async_executor_example.py`：

1. **基本使用示例** (`example_basic_usage`)
2. **多任务管理示例** (`example_multiple_tasks`)
3. **实时输出查看** (`example_realtime_output`)
4. **自动清理说明** (`example_auto_cleanup`)

## 🔧 实现细节

### 文件结构

```
src/
├── async_executor.py    # 后台任务执行模块
│   ├── ByteLimitedBuffer      # 字节限制环形缓冲区
│   ├── BackgroundTask         # 任务对象
│   ├── TaskSummary            # 任务摘要
│   └── BackgroundTaskManager  # 任务管理器
└── core/client.py       # SSHClient集成（已更新）
```

### 关键设计决策

1. **环形缓冲区**：使用`collections.deque`实现字节限制，自动丢弃旧数据
2. **自动清理**：使用`threading.Timer`，1小时后自动从管理器移除
3. **名称管理**：字典存储，名称重复立即报错
4. **停止方式**：先发送Ctrl+C（SIGINT），超时后强制关闭channel
5. **远程文件检测**：解析`-w`参数，自动识别tcpdump输出文件路径

## 📝 日志输出

任务完成时自动记录：

```
# 任务自己完成
2025-02-14 10:00:45 | INFO | 后台任务完成 [a3f7b2d] tcpdump -i eth0... | 退出码: 0 | 时长: 45.2s | 输出: 0行/0B
2025-02-14 10:00:45 | DEBUG | 任务 [a3f7b2d] 将在 3600s 后自动清理
2025-02-14 11:00:45 | DEBUG | 任务 [a3f7b2d] 已从管理器自动清理

# 被手动停止
2025-02-14 10:05:00 | INFO | 后台任务停止 [b8e9c1a] tcpdump -i eth0... | 时长: 120.0s | 原因: 用户优雅停止
```

## ✅ 测试验证

```bash
# 运行所有单元测试
python -m pytest tests/unit -x

# 结果
676 passed, 3 skipped  # ✅ 全部通过
```

## 🔄 与Paramiko解耦的关系

此模块基于Paramiko解耦架构实现：
- 使用 `BackendFactory` 创建后端连接
- 使用抽象 `Channel` 类型执行命令
- 完全兼容解耦后的SSHClient

## 📦 Git提交记录

```bash
# 最新提交
dd22f9c feat(async): 添加后台任务执行模块 - 支持tcpdump等长时间命令非阻塞执行
```

**提交内容：**
- ✨ 新增 `src/async_executor.py` (657行)
- 📝 新增 `examples/async_executor_example.py` (239行)
- 🔧 更新 `src/core/client.py` 集成后台任务方法

---

**版本**: 1.2.0  
**日期**: 2025-02-14  
**状态**: ✅ 已完成并测试通过
