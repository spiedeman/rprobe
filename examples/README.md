# RemoteSSH 使用示例

这里包含了 RemoteSSH 的各种使用示例，帮助您快速上手。

## 📁 示例列表

### 1. basic_usage.py - 基本用法
展示SSHClient的核心功能：
- 执行基本命令
- 使用连接池
- 错误处理
- Shell会话

```bash
python examples/basic_usage.py
```

### 2. batch_operations.py - 批量操作
多服务器管理和批量操作：
- 检查所有服务器状态
- 并行执行命令
- 批量重启服务
- 文件部署

```bash
python examples/batch_operations.py
```

### 3. config_examples.py - 配置加载
从不同来源加载配置：
- 基本配置创建
- YAML/JSON文件
- 环境变量
- 配置合并和验证

```bash
python examples/config_examples.py
```

### 4. monitoring.py - 监控和日志
结构化日志和性能监控：
- 简单日志配置
- JSON格式日志
- 上下文绑定
- 性能对比
- 连接池统计

```bash
python examples/monitoring.py
```

### 5. advanced_patterns.py - 高级模式
高级用法和最佳实践：
- 上下文管理器
- 命令管道
- 文件操作
- 服务管理
- 备份脚本
- 健康检查
- 多服务器任务
- Shell交互

```bash
python examples/advanced_patterns.py
```

## 🚀 快速开始

### 1. 配置SSH连接

在运行示例前，请修改示例代码中的SSH配置：

```python
config = SSHConfig(
    host="your-server.com",      # 服务器地址
    username="your-username",    # 用户名
    password="your-password",    # 密码
    # 或使用密钥：
    # key_filename="/path/to/key",
)
```

### 2. 运行单个示例

取消示例文件中对应函数的注释：

```python
if __name__ == "__main__":
    # 取消注释要运行的示例
    example_1_basic_command()
    # example_2_with_pool()
```

### 3. 使用环境变量

更安全的方式是使用环境变量：

```bash
export SSH_HOST="your-server.com"
export SSH_USER="your-username"
export SSH_PASS="your-password"

python examples/basic_usage.py
```

## 💡 常见用法

### 执行命令

```python
from src import SSHClient, SSHConfig

config = SSHConfig(host="server.com", username="user", password="pass")

with SSHClient(config) as client:
    result = client.exec_command("ls -la")
    print(result.stdout)
```

### 使用连接池

```python
# 启用连接池，复用连接
client = SSHClient(config, use_pool=True, max_size=5)

# 执行多个命令（自动复用连接）
for cmd in commands:
    result = client.exec_command(cmd)

client.disconnect()
```

### 交互式Shell

```python
with SSHClient(config) as client:
    # 打开Shell会话
    client.open_shell_session()
    
    # 执行命令（保持状态）
    client.shell_command("cd /tmp")
    result = client.shell_command("pwd")
    print(result.stdout)  # /tmp
    
    client.close_shell_session()
```

### 从文件加载配置

```python
from src import load_config

# 从YAML文件加载
config = load_config(file_path="config.yaml")

# 或使用环境变量
config = load_config(use_env=True)

with SSHClient(config) as client:
    result = client.exec_command("whoami")
```

## 🔧 配置示例

### YAML配置 (config.yaml)

```yaml
host: production.server.com
username: deploy
password: secret123
port: 22
timeout: 30.0
command_timeout: 300.0
max_output_size: 10485760
```

### JSON配置 (config.json)

```json
{
    "host": "api.server.com",
    "username": "api_user",
    "password": "api_pass",
    "port": 22,
    "recv_mode": "select"
}
```

### 环境变量

```bash
export REMOTE_SSH_HOST="server.com"
export REMOTE_SSH_USERNAME="user"
export REMOTE_SSH_PASSWORD="pass"
export REMOTE_SSH_PORT="22"
```

## 📊 性能提示

### 使用连接池

```python
# 连接池能显著提升性能
# 5个命令：无池约5秒，有池约1秒

client = SSHClient(config, use_pool=True, max_size=5)
# ... 执行多个命令
client.disconnect()
```

### 选择合适的接收模式

```python
# Linux/Mac 使用 select 模式（CPU占用0%）
config = SSHConfig(..., recv_mode="select")

# Windows 使用 adaptive 模式
config = SSHConfig(..., recv_mode="adaptive")
```

## 🛡️ 安全最佳实践

1. **不要在代码中硬编码密码**
   ```python
   # ❌ 不要这样做
   config = SSHConfig(host="x", username="y", password="secret123")
   
   # ✅ 使用环境变量
   import os
   config = SSHConfig(
       host=os.getenv("SSH_HOST"),
       username=os.getenv("SSH_USER"),
       password=os.getenv("SSH_PASS")
   )
   ```

2. **使用密钥认证**
   ```python
   config = SSHConfig(
       host="server.com",
       username="user",
       key_filename="/home/user/.ssh/id_rsa"
   )
   ```

3. **限制密钥文件权限**
   ```bash
   chmod 600 /path/to/key
   ```

4. **使用配置文件**
   ```python
   # 将敏感信息放在配置文件
   config = load_config(file_path="config.yaml")
   ```

## 📚 更多资源

- [API文档](../PROJECT_STATUS.md)
- [性能优化指南](../docs/performance_optimization.md)
- [测试示例](../tests/README.md)

## 🤝 贡献

如果您有实用的示例想要分享，欢迎提交Pull Request！
