# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **可插拔后端架构** - 创建SSHBackend抽象基类，支持多种SSH库实现
- **Paramiko后端实现** - 将paramiko封装为独立后端模块
- **后端工厂模式** - BackendFactory支持动态后端注册和创建
- **抽象异常体系** - 定义与具体SSH库无关的异常类（AuthenticationError, ConnectionError, SSHException, ChannelException）
- **68个新增测试** - 白盒测试（28个）+ 黑盒测试（24个）+ 集成测试（16个）
- **流式数据传输API** - `exec_command_stream()` 支持超大数据传输，内存占用O(1)
- **测试配置集中管理** - 支持环境变量控制测试强度
- **集成测试优化** - 执行时间从401秒缩短至约120秒（70%提升）
- 后端架构完整文档（5个新文档）

### Changed
- **重大重构**：解耦paramiko依赖，所有核心模块改为使用抽象后端
  - `src/core/connection.py` - ConnectionManager使用BackendFactory
  - `src/core/client.py` - SSHClient使用抽象异常
  - `src/session/shell_session.py` - 使用抽象Channel类型
  - `src/receivers/` - 所有接收器使用抽象类型注解
- **异常处理**：所有异常改为使用抽象层定义的异常类，保持向后兼容
- **ConnectionError继承**：改为继承Python内置ConnectionError以提高兼容性
- **优化SSH数据接收逻辑** - 改进流式接收器完成判断
  - 基于"数据静默期"的智能算法（100ms无数据即完成）
  - 最大等待时间1秒，平衡速度和可靠性
  - 渐进式检查间隔减少CPU占用

### Removed
- 核心模块中的直接 `import paramiko` 依赖
- 硬编码的paramiko类型注解

## [1.1.0] - 2026-02-10

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
