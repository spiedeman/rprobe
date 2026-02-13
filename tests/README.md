# RemoteSSH 测试

## 测试统计

- **单元测试**: 618个（100%通过，~3.7秒）
- **集成测试**: 82个（98.8%通过，~122秒）
- **代码覆盖率**: 92%

## 快速运行

```bash
# 单元测试（推荐）
TESTING=true python -m pytest tests/unit -v

# 集成测试（需要SSH服务器）
export TEST_REAL_SSH=true
export TEST_SSH_HOST=your-host
export TEST_SSH_USER=your-user
export TEST_SSH_PASS=your-pass
python -m pytest tests/integration -v --run-integration
```

## 目录结构

```
tests/
├── conftest.py              # Pytest配置
├── unit/                    # 单元测试（618个）
│   ├── test_config.py
│   ├── test_client.py
│   ├── test_pool_*.py       # 连接池相关
│   └── test_multi_session_manager.py
└── integration/             # 集成测试（82个）
    ├── test_ssh_integration.py
    ├── test_pool_features.py
    ├── test_multi_session.py
    └── test_supplemental.py
```

## 编写测试

### 单元测试

```python
# tests/unit/test_feature.py
import pytest
from unittest.mock import Mock, patch

class TestFeature:
    def test_something(self):
        with patch('paramiko.SSHClient') as mock_client:
            # 测试代码
            pass
```

### 集成测试

```python
# tests/integration/test_feature.py
import pytest

@pytest.mark.integration
class TestFeature:
    def test_real_ssh(self, test_environment):
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实SSH环境")
        # 测试代码
```

## 测试命名规范

- **文件**: `test_<module>.py`
- **类**: `Test<Feature>`
- **方法**: `test_<description>`
- **集成测试**: 使用 `@pytest.mark.integration`

## 覆盖率报告

```bash
python -m pytest tests/unit --cov=src --cov-report=html
```
