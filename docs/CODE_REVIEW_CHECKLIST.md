# 代码审查检查清单 (Code Review Checklist)

本清单用于确保代码审查时覆盖所有关键检查点，特别是在处理解耦架构、连接池和异常处理时。

## 🏗️ 架构设计检查

### 接口完整性
- [ ] **所有抽象方法都已实现**: 检查具体类是否实现了抽象基类/协议的所有方法
- [ ] **新增方法已添加到契约测试**: 如果有新增方法，确保契约测试已更新
- [ ] **返回类型注解完整**: 所有公共API都有返回类型注解
- [ ] **参数类型注解完整**: 所有参数都有类型注解

**工具**: 运行 `pytest tests/contracts/test_backend_contract.py -v`

### 解耦架构检查
- [ ] **后端接口一致性**: 所有后端实现（ParamikoBackend等）遵循相同接口
- [ ] **异常映射完整**: 所有后端特定异常都有映射到自定义异常
- [ ] **Channel方法完整**: Channel实现包含所有被调用的方法（特别是get_transport）
- [ ] **Transport方法完整**: Transport实现包含所有必需方法

---

## 🔌 连接池检查

### 上下文管理器
- [ ] **正确使用 with 语句**: `pool.get_connection()` 必须使用 `with` 或 `__enter__/__exit__`
- [ ] **资源释放保证**: 确保在 finally 块或使用上下文管理器释放资源
- [ ] **无直接调用**: 不能直接从上下文管理器对象调用方法（如 `conn.open_channel`）

**错误示例**:
```python
# ❌ 错误
conn = pool.get_connection()
channel = conn.open_channel()  # GeneratorContextManager 没有此方法
```

**正确示例**:
```python
# ✅ 正确
with pool.get_connection() as conn:
    channel = conn.open_channel()
```

### 连接生命周期
- [ ] **连接正确关闭**: 确保连接在异常情况下也能关闭
- [ ] **无连接泄漏**: 使用连接池后，连接必须归还
- [ ] **超时处理**: 获取连接和命令执行都有超时设置

---

## ⚠️ 异常处理检查

### 异常映射
- [ ] **统一异常类型**: 相同错误使用相同的自定义异常
- [ ] **异常链完整**: 使用 `raise ... from e` 保留原始异常信息
- [ ] **消息清晰**: 异常消息清晰描述问题和上下文

### 异常覆盖
- [ ] **认证异常**: `paramiko.AuthenticationException` → `AuthenticationError`
- [ ] **连接异常**: 网络错误 → `ConnectionError`
- [ ] **SSH异常**: 协议错误 → `SSHException`
- [ ] **通道异常**: 通道操作错误 → `ChannelException`

**工具**: 使用 `ExceptionMapper` 注册新的异常映射

---

## 🧪 测试覆盖检查

### 单元测试
- [ ] **Mock保真度**: Mock对象是否忠实模拟真实对象的行为
- [ ] **边界条件**: 测试空值、最大值、异常输入等边界
- [ ] **异常路径**: 测试所有异常处理分支

### 集成测试
- [ ] **真实环境**: 关键功能是否能在真实SSH环境运行
- [ ] **环境独立性**: 测试不应依赖特定网络环境（除非专门测试网络）
- [ ] **资源清理**: 测试后是否正确清理资源

**运行命令**:
```bash
# 单元测试
pytest tests/unit -v

# 集成测试（需要真实SSH服务器）
export TEST_REAL_SSH=true
pytest tests/integration -v --run-integration

# 契约测试
pytest tests/contracts -v
```

---

## 📊 性能与可观测性

### 日志
- [ ] **关键路径日志**: 连接、断开、错误等关键操作有日志
- [ ] **结构化日志**: 使用 extra 参数添加上下文信息
- [ ] **适当日志级别**: DEBUG用于调试，INFO用于关键事件，ERROR用于错误

**示例**:
```python
logger.info("SSH连接成功", extra={
    "host": host,
    "port": port,
    "backend": type(backend).__name__
})
```

### 性能
- [ ] **无阻塞操作**: 网络操作应有超时设置
- [ ] **资源复用**: 使用连接池而非每次都新建连接
- [ ] **避免重复计算**: 缓存昂贵的计算结果

---

## 📋 具体场景检查清单

### 添加新的后端实现
1. [ ] 实现 `SSHBackend` 抽象基类的所有方法
2. [ ] 实现 `Channel` 包装器，包含所有必需方法
3. [ ] 实现 `Transport` 包装器
4. [ ] 注册异常映射
5. [ ] 添加契约测试
6. [ ] 运行集成测试验证

### 修改 Channel 相关代码
1. [ ] 检查所有调用方使用的 channel 方法
2. [ ] 确保这些方法在 Channel 实现中存在
3. [ ] 更新契约测试
4. [ ] 运行单元测试和集成测试

### 修改连接池相关代码
1. [ ] 正确使用上下文管理器模式
2. [ ] 确保连接正确释放
3. [ ] 测试高并发场景
4. [ ] 检查资源泄漏

### 修改异常处理代码
1. [ ] 确保所有异常都映射到自定义异常
2. [ ] 使用 `raise ... from e` 保留异常链
3. [ ] 更新相关测试的异常期望
4. [ ] 运行测试验证异常类型

---

## 🔧 审查工具

### 自动化检查
```bash
# 类型检查
mypy src/rprobe

# 代码风格
black --check src/ tests/
flake8 src/ tests/

# 运行契约测试
pytest tests/contracts -v

# 运行所有测试
pytest tests/unit tests/integration --run-integration -v
```

### 手动检查点
- [ ] 代码是否清晰易读
- [ ] 命名是否准确反映意图
- [ ] 是否有冗余代码可以简化
- [ ] 注释是否必要且准确
- [ ] 文档是否已更新

---

## 📝 审查记录模板

```markdown
## 审查记录

**提交**: [commit hash]
**审查者**: [name]
**日期**: [date]

### 检查项
- [x] 接口完整性
- [x] 连接池使用
- [x] 异常映射
- [x] 测试覆盖
- [x] 日志可观测性

### 发现的问题
1. [问题描述] - [解决方案]

### 建议
- [改进建议]

### 结论
- [ ] 通过
- [ ] 需修改
- [ ] 有条件通过
```

---

## 💡 常见问题与解决方案

### Q: 如何检查 ParamikoChannel 是否缺少方法？
**A**: 运行契约测试
```bash
pytest tests/contracts/test_backend_contract.py::TestBackendInterfaceContract::test_channel_has_required_methods -v
```

### Q: 上下文管理器使用错误的常见症状？
**A**: `AttributeError: '_GeneratorContextManager' object has no attribute 'xxx'`
**解决**: 使用 `with ... as conn:` 而不是直接赋值

### Q: 如何确保异常映射完整？
**A**: 在 `ExceptionMapper` 中注册所有新异常，并运行异常契约测试

---

**最后更新**: 2026-03-01
**版本**: 1.0
