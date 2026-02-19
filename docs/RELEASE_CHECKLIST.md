# 发布检查清单

## Pre-Release Checklist

### 代码质量检查
- [x] 所有测试通过 (808 tests passing)
- [x] 代码格式化 (black)
- [x] 代码风格检查 (flake8)
- [ ] 更新 CHANGELOG.md
- [ ] 更新版本号
- [ ] 创建 Git tag

### 功能验证
- [ ] 基本 SSH 连接测试
- [ ] 连接池功能测试
- [ ] 后台任务执行测试
- [ ] 流式数据处理测试
- [ ] ConnectionFactory 功能测试

### 文档检查
- [ ] README.md 已更新
- [ ] API 文档完整
- [ ] 示例代码可运行
- [ ] 安装指南最新

### 集成测试
- [ ] 真实 SSH 服务器测试（可选）
- [ ] 性能基准测试
- [ ] 内存泄漏检查

## Release Steps

### 1. 版本准备
```bash
# 更新版本号
# 在 pyproject.toml 或 __init__.py 中更新版本

# 更新 CHANGELOG.md
# 添加新版本条目
```

### 2. 最终检查
```bash
# 运行完整测试
python -m pytest tests/unit -v

# 运行代码质量检查
python -m black src/ tests/ --check
python -m flake8 src/ tests/

# 检查覆盖率
python -m pytest tests/unit --cov=src --cov-report=term
```

### 3. 创建发布
```bash
# 提交所有更改
git add -A
git commit -m "release: prepare v1.4.0"

# 创建 tag
git tag -a v1.4.0 -m "Release version 1.4.0"

# 推送到远程
git push origin main
git push origin v1.4.0
```

### 4. 发布验证
- [ ] GitHub Release 已创建
- [ ] PyPI 包已发布（如适用）
- [ ] 文档网站已更新
- [ ] 发布公告已发送

## Post-Release

### 监控
- [ ] 检查错误报告
- [ ] 监控性能指标
- [ ] 收集用户反馈

### 后续计划
- [ ] 规划下一个版本
- [ ] 更新路线图
- [ ] 安排维护窗口
