# AGENTS.md - rprobe 项目

此文件包含在此代码库中工作的代理编码人员的指南和命令。

## 项目概述

这是一个轻量级的远程SSH探针工具，用于快速手动测试和远程设备探查。

## 开发环境设置（⚠️ 必须使用虚拟环境）

### 1. 创建并激活虚拟环境

```bash
# 创建虚拟环境（仅需执行一次）
python3 -m venv .venv

# 激活虚拟环境（⚠️ 每次开发前必须执行）
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 验证虚拟环境已激活
which python  # 应显示 .venv/bin/python
```

### 2. 安装依赖

```bash
# 确保虚拟环境已激活（提示符前有 (.venv)）

# 安装项目依赖
pip install -e .

# 安装开发依赖
pip install pytest pytest-cov black flake8 mypy pre-commit isort bandit

# 安装预提交钩子
pre-commit install
pre-commit install --hook-type commit-msg
```

### 3. 退出虚拟环境

```bash
deactivate
```

### 运行应用程序
```bash
python main.py
```

### 运行应用程序
```bash
# 确保虚拟环境已激活
source .venv/bin/activate

python main.py
```

### 测试（⚠️ 必须先激活虚拟环境）

**重要：运行测试前必须确保虚拟环境已激活！**

```bash
# 1. 激活虚拟环境
source .venv/bin/activate

# 2. 运行所有测试
python -m pytest

# 3. 运行单元测试（快速，约3秒）
TESTING=true python -m pytest tests/unit -v

# 4. 运行特定测试文件
python -m pytest tests/unit/test_client.py -v

# 5. 运行覆盖率测试
python -m pytest tests/unit --cov=. --cov-report=html

# 6. 运行集成测试（需要真实SSH服务器）
export TEST_REAL_SSH=true
export TEST_SSH_HOST=your-host
export TEST_SSH_USER=your-user
export TEST_SSH_PASS=your-pass
python -m pytest tests/integration --run-integration -v
```

### 代码检查和格式化（⚠️ 必须先激活虚拟环境）

**重要：运行代码检查前必须确保虚拟环境已激活！**

```bash
# 确保虚拟环境已激活
source .venv/bin/activate

# 使用flake8进行代码检查
flake8 .

# 使用black进行格式化
black .

# 使用mypy进行类型检查
mypy .

# 使用isort进行导入排序
isort .

# 使用bandit进行安全检查
bandit -r src/
```

## 开发工作流程（修改代码后必做）

### 步骤1: 静态代码检查（⚠️ 必须在测试前执行）

**每次修改代码后，必须先运行静态代码检查！**

```bash
# 1. 确保虚拟环境已激活
source .venv/bin/activate

# 2. 运行代码格式化（black）
black src/ tests/ examples/

# 3. 运行导入排序检查（isort）
isort src/ tests/ examples/ --check-only --diff

# 4. 运行代码风格检查（flake8）
flake8 src/ tests/ examples/ --count --statistics

# 5. 运行类型检查（mypy）- 最重要！
mypy src/ --ignore-missing-imports

# 6. 运行安全检查（bandit）
bandit -r src/ -f json
```

**或者使用快捷脚本：**
```bash
# 创建快捷脚本（添加到 ~/.bashrc 或 ~/.zshrc）
alias lint='black src/ tests/ examples/ && isort src/ tests/ examples/ && flake8 src/ tests/ examples/ && mypy src/ --ignore-missing-imports && bandit -r src/'

# 使用
lint
```

### 步骤2: 运行测试

只有在静态代码检查通过后，才运行测试：

```bash
# 运行单元测试
TESTING=true python -m pytest tests/unit -v

# 运行特定测试
TESTING=true python -m pytest tests/unit/test_client.py -v
```

### 步骤3: 提交代码

```bash
# 检查修改的文件
git status

# 添加修改的文件
git add <modified-files>

# 提交（使用约定式提交消息）
git commit -m "type(scope): description"
```

### 代码检查检查清单

修改代码后，在运行测试前必须确认：

- [ ] **Black** - 代码已格式化
- [ ] **isort** - 导入已排序
- [ ] **Flake8** - 无代码风格错误
- [ ] **mypy** - 无类型错误（**强制要求**）
- [ ] **bandit** - 无安全问题
- [ ] **测试** - 所有测试通过

### 为什么先运行静态检查？

1. **尽早发现问题** - 在运行测试前发现类型错误和风格问题
2. **节省测试时间** - 避免因类型错误导致的测试失败
3. **保持代码质量** - 确保每次提交都符合代码规范
4. **CI/CD 要求** - GitHub Actions 会运行相同的检查

### 常见问题

**Q: mypy 报告 "Library stubs not installed" 错误？**
```bash
# 安装类型 stubs
pip install types-paramiko types-PyYAML
# 或者
mypy --install-types
```

**Q: 如何忽略特定行的类型检查？**
```python
# type: ignore
result = some_function()  # type: ignore
```

**Q: 如何查看详细的类型错误？**
```bash
mypy src/ --ignore-missing-imports --show-error-codes
```

## 代码风格指南

### 导入风格
- 使用绝对导入
- 按组导入：标准库、第三方库、本地导入
- 将导入语句放在文件顶部
- 使用 `import paramiko` 而不是 `from paramiko import *`

### 代码格式化
- 遵循PEP 8标准
- 使用4个空格缩进
- 最大行长度：88个字符（black标准）
- 使用black进行自动格式化

### 类型提示
- 为所有函数签名添加类型提示
- 使用Python 3.6+类型注解语法
- 根据需要导入typing构造：`from typing import Optional, List, Dict`

### 命名约定
- 变量和函数：`snake_case`
- 类：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`
- 私有成员：使用下划线前缀 `_private_method`

### 错误处理
- 对SSH操作使用try-except块
- 处理paramiko特定异常（SSHException、AuthenticationException等）
- 适当记录错误而不暴露敏感信息
- 始终在finally块中关闭SSH连接

### 安全最佳实践
- 绝不在源代码中硬编码凭据
- 使用环境变量或配置文件存储SSH密钥/密码
- 验证所有用户输入
- 使用正确的密钥文件权限（600）
- 考虑在适当时使用SSH代理转发

### 文档
- 为所有公共函数和类添加文档字符串
- 使用Google风格或NumPy风格的文档字符串
- 包含参数类型、返回类型和引发的异常
- 为复杂逻辑添加内联注释

### SSH连接模式
```python
import paramiko
from typing import Optional

def create_ssh_client(hostname: str, username: str, key_filename: Optional[str] = None) -> paramiko.SSHClient:
    """创建并返回SSH客户端连接。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(hostname=hostname, username=username, key_filename=key_filename)
        return client
    except paramiko.AuthenticationException:
        # 处理身份验证错误
        raise
    except paramiko.SSHException as e:
        # 处理SSH连接错误
        raise
```

## 测试指南

- 使用模拟为所有SSH操作编写单元测试
- 使用pytest夹具设置SSH客户端
- 在测试中模拟paramiko调用以避免实际网络连接
- 测试错误处理路径
- 目标代码覆盖率>80%

## Git工作流

- 使用约定式提交消息：`feat:`、`fix:`、`docs:`、`refactor:`等
- 保持提交小而专注
- 确保在提交前所有测试通过
- 在提交前运行代码检查和格式化

## 性能考虑

- 尽可能重用SSH连接
- 为多个操作实现连接池
- 对并发SSH操作使用async/await模式（如果使用asyncssh）
- 适当处理连接超时
- 考虑对大文件传输使用压缩