# SSH Client 单元测试

## 目录结构

```
tests/
├── conftest.py              # Pytest 配置和共享夹具
├── README.md                # 本文件
├── unit/                    # 单元测试目录（使用 Mock，无需真实 SSH）
│   ├── __init__.py
│   ├── test_config.py       # SSHConfig 配置测试
│   ├── test_client.py       # SSHClient 连接管理测试
│   ├── test_exec_command.py # exec_command 功能测试
│   ├── test_shell_command.py# shell_command 功能测试
│   └── test_result.py       # CommandResult 测试
└── integration/             # 集成测试目录（需要真实 SSH 服务器）
    ├── __init__.py
    └── test_ssh_integration.py  # 真实 SSH 服务器测试
```

## 安装依赖

```bash
pip install pytest pytest-cov
```

## 运行测试

### 运行单元测试（推荐，默认）

单元测试使用 Mock 模拟 SSH 连接，无需真实服务器，运行速度快：

```bash
# 运行所有单元测试
python -m pytest tests/unit/ -v

# 运行特定单元测试文件
python -m pytest tests/unit/test_config.py -v
python -m pytest tests/unit/test_exec_command.py -v

# 生成覆盖率报告
python -m pytest tests/unit/ --cov=src --cov-report=html
```

### 运行集成测试（可选）

集成测试需要真实 SSH 服务器：

```bash
# 设置环境变量
export TEST_REAL_SSH=true
export TEST_SSH_HOST=your-host
export TEST_SSH_USER=your-user
export TEST_SSH_PASS=your-password

# 运行集成测试
python -m pytest tests/integration/ -v --run-integration

# 同时运行单元测试和集成测试
python -m pytest tests/ -v --run-integration
```

## 测试类别

### 1. 单元测试 (tests/unit/)

**特点：**
- 使用 Mock 模拟 SSH 连接
- 无需真实 SSH 服务器
- 运行速度快（约 10 秒）
- 适合 CI/CD 环境

**覆盖范围：**
- ✅ SSHConfig 配置验证
- ✅ SSHClient 连接管理
- ✅ exec_command 命令执行
- ✅ shell_command 会话管理
- ✅ CommandResult 数据处理
- ✅ 错误处理和异常
- ✅ 网络异常模拟

### 2. 集成测试 (tests/integration/)

**特点：**
- 需要真实 SSH 服务器
- 测试端到端功能
- 运行速度较慢（依赖网络）
- 适合发布前验证

**覆盖范围：**
- ✅ 真实 SSH 连接
- ✅ exec 命令执行
- ✅ shell 会话管理
- ✅ 连接复用

## 测试覆盖率

当前单元测试覆盖:
- ✅ SSHConfig 配置验证
- ✅ SSHClient 连接管理
- ✅ exec_command 命令执行
- ✅ shell_command 会话管理
- ✅ CommandResult 数据处理
- ✅ 错误处理和异常
- ✅ 网络异常模拟

## 编写新测试

### 编写单元测试

在 `tests/unit/` 目录下创建新文件：

```python
# tests/unit/test_new_feature.py
import pytest
from unittest.mock import Mock, patch

class TestNewFeature:
    """测试新功能"""
    
    def test_something(self, mock_ssh_config):
        """测试某个功能"""
        from src.infrastructure import SSHClient
        
        client = SSHClient(mock_ssh_config)
        
        with patch('paramiko.SSHClient') as mock_client:
            # 设置 mock
            # 执行测试
            # 验证结果
            pass
```

### 编写集成测试

在 `tests/integration/` 目录下创建新文件：

```python
# tests/integration/test_new_integration.py
import pytest
from src.infrastructure import SSHConfig, SSHClient

@pytest.mark.integration
class TestNewIntegration:
    """新集成测试"""
    
    def test_real_ssh_feature(self, test_environment):
        """测试真实 SSH 功能"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(...)
        with SSHClient(config) as client:
            # 测试真实功能
            pass
```

## 测试命名规范

- **测试文件**: `test_<module_name>.py`
- **测试类**: `Test<ClassName>` 或 `Test<FeatureName>`
- **测试方法**: `test_<description>`
- **集成测试**: 使用 `@pytest.mark.integration` 标记

## 运行单个测试

```bash
# 运行单个测试方法
python -m pytest tests/unit/test_config.py::TestSSHConfig::test_valid_password_config -v

# 运行单个测试类
python -m pytest tests/unit/test_config.py::TestSSHConfig -v
```
