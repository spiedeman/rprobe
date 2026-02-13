# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 连接池统计人类可读格式（ms/s/m/h/d）
- 连接池关闭后复用和重置功能
- PoolManager 增强（create_pool, close_pool, get_pool, remove_pool, list_pools）
- 连接池连接管理（关闭特定ID、批量关闭、空闲关闭、条件过滤）
- 多会话管理器（MultiSessionManager）支持单连接多Shell
- 架构对比文档和示例代码
- 64个新增单元测试

## [1.1.0] - 2026-02-10

### Added
- 初始化 Git 版本控制
- 添加 GitHub Actions CI/CD 工作流
- 添加预提交钩子配置（pre-commit）
- 添加代码质量检查（Black, isort, flake8, mypy, bandit）
- 添加分支保护策略文档
- 添加 Git 工作流使用指南
- 配置语义化版本发布（semantic-release）

### Changed
- 优化单元测试性能（23秒→2.72秒，88%提升）
- 修复慢测试问题（10秒→0.08秒）
- 完善项目配置（pyproject.toml）

## [1.0.0] - 2026-02-09

### Added
- 高性能 Python SSH 客户端库
- 连接池管理（支持并行创建）
- 结构化日志系统
- 多源配置支持（代码、YAML/JSON、环境变量）
- Shell 会话管理（交互式支持）
- 572个测试，92%代码覆盖率
- 参数化测试、压力测试、安全测试
