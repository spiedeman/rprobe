# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.0] - 2026-02-19

### Added
- **后台任务执行器** - 非阻塞执行长时间命令（如tcpdump）
  - `SSHClient.bg()` 方法启动后台任务
  - 字节限制环形缓冲区（默认10MB）防止内存溢出
  - 任务完成自动记录日志，1小时后自动清理
  - 支持通过名称管理多个后台任务
  - 优雅停止和强制停止选项
  - 轻量级摘要接口 `get_summary()`，不下载完整输出
- **ConnectionFactory** - 统一封装Channel创建，消除重复代码
  - 支持多种Channel类型：exec、shell
  - 使用上下文管理器确保资源正确释放
  - 支持连接池和直接连接两种模式
  - 自动错误处理和清理
- **98个新增测试** - 大幅提升测试覆盖率
  - `test_async_executor.py` - 48个测试（81.86%覆盖率）
  - `test_performance_monitor.py` - 19个测试（86.67%覆盖率）
  - `test_connection_factory.py` - 31个测试（91.45%覆盖率）
  - `test_channel_receiver_optimized_extended.py` - 补充测试
- **Mock工厂** - 提供标准化的Mock对象创建
  - `SSHMockFactory` - 创建Transport、Channel、SSHClient等Mock
  - `MockBuilder` - 链式API构建复杂Mock
  - `create_mock_ssh_setup()` - 一键创建完整SSH环境
- **代码质量工具**
  - `.flake8` 配置文件（与black兼容）
  - `scripts/check_quality.sh` - 自动化代码质量检查

### Changed
- **代码格式化** - 使用black格式化87个文件
- **测试修复** - 修复`test_retry_backoff_delay`，移除全局time.sleep patch
- **Bug修复** - `TaskSummary`添加缺少的`bytes_stderr`字段
- **文档更新** - README.md添加新特性说明和示例

### Removed
- 清理14个临时文档文件

## [1.3.0] - 2026-02-15

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
