# Git 工作流总览

> **项目**: RemoteSSH - 高性能 Python SSH 客户端库  
> **版本**: 1.1.0  
> **最后更新**: 2026-02-10

---

## 🎯 现代化 Git 工作流已完成

本项目已配置完整的现代化 Git 版本管理策略，包括：

✅ **Git 版本控制** - 仓库已初始化  
✅ **分支管理策略** - GitHub Flow  
✅ **提交规范** - Conventional Commits  
✅ **CI/CD 自动化** - GitHub Actions  
✅ **代码质量门禁** - pre-commit 钩子  
✅ **并行开发支持** - Git worktrees  
✅ **语义化版本发布** - semantic-release  
✅ **完整文档** - 使用指南和策略文档

---

## 📁 新增文件清单

### 配置文件
```
.gitignore                    # Git 忽略规则
.pre-commit-config.yaml       # 预提交钩子配置
pyproject.toml                # 项目配置和工具设置
LICENSE                       # MIT 许可证
CHANGELOG.md                  # 版本变更日志
```

### GitHub Actions 工作流
```
.github/workflows/
├── ci.yml                    # 持续集成（测试、代码质量）
└── release.yml               # 自动发布（标签、PyPI）
```

### 文档
```
docs/git-workflow/
├── branch-protection.md      # 分支保护策略
└── guide.md                  # 完整使用指南
```

---

## 🚀 快速开始

### 1. 安装开发依赖

```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

### 2. 安装预提交钩子

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

### 3. 验证环境

```bash
# 运行测试
TESTING=true python -m pytest tests/unit -v

# 检查代码质量
black --check .
flake8 .
mypy src/
```

---

## 📋 工作流概览

### 分支策略（GitHub Flow）

```
main ─────────────────────────────────────────────
       │              │              │
       ▼              ▼              ▼
   feature/a    feature/b    hotfix/critical
       │              │              │
       └──────────────┴──────────────┘
                      │
                      ▼
                  PR → Review → Merge
```

| 分支 | 用途 | 保护级别 |
|------|------|----------|
| `main` | 生产代码 | 🔴 严格保护 |
| `develop` | 集成开发 | 🟡 中等保护 |
| `feature/*` | 功能开发 | 🟢 无保护 |
| `hotfix/*` | 紧急修复 | 🟢 无保护 |

### 提交规范

```bash
# 格式: type(scope): subject

git commit -m "feat(pool): 添加连接池并行创建"
git commit -m "fix(client): 修复超时处理"
git commit -m "docs: 更新API文档"
git commit -m "test: 添加压力测试"
```

**类型**: `feat` `fix` `docs` `style` `refactor` `test` `chore` `perf` `ci` `revert`

### 开发流程

```bash
# 1. 使用 worktree 创建隔离工作空间
git worktree add .worktrees/feature-x feature/x
cd .worktrees/feature-x

# 2. 开发代码
# ...

# 3. 提交更改
git add .
git commit -m "feat: 实现新功能"

# 4. 推送并创建 PR
git push -u origin feature/x
gh pr create --title "feat: xxx" --body "..."

# 5. 合并后清理
git worktree remove .worktrees/feature-x
```

---

## 🔒 自动化检查

### 预提交钩子（本地）

每次提交前自动运行：
- ✅ **Trailing whitespace** 清理
- ✅ **EOF fixer** 修复
- ✅ **Black** 代码格式化
- ✅ **isort** 导入排序
- ✅ **flake8** 代码检查
- ✅ **bandit** 安全检查
- ✅ **commitizen** 提交信息检查

### CI/CD 流水线（云端）

每次推送/PR 自动运行：
- ✅ **多版本 Python 测试** (3.9, 3.10, 3.11, 3.12)
- ✅ **单元测试** + 覆盖率报告
- ✅ **代码质量检查** (Black, flake8, mypy)
- ✅ **Codecov** 覆盖率上传

### 发布流程

推送到 `main` 分支后自动：
- ✅ 分析提交历史生成版本号
- ✅ 更新 `CHANGELOG.md`
- ✅ 创建 Git Tag
- ✅ 创建 GitHub Release
- ✅ 发布到 PyPI（配置 Token 后）

---

## 📚 详细文档

| 文档 | 内容 | 位置 |
|------|------|------|
| **分支保护策略** | 分支规则、提交规范、审查清单 | `docs/git-workflow/branch-protection.md` |
| **使用指南** | 完整工作流、命令示例、故障排除 | `docs/git-workflow/guide.md` |
| **项目状态** | 当前进度、测试统计、性能指标 | `PROJECT_STATUS.md` |
| **变更日志** | 版本历史和变更记录 | `CHANGELOG.md` |

---

## 🛠️ 工具配置

### pyproject.toml 包含

- **Black** - 代码格式化配置
- **isort** - 导入排序配置
- **pytest** - 测试运行配置
- **coverage** - 代码覆盖率配置
- **mypy** - 类型检查配置
- **bandit** - 安全检查配置
- **semantic_release** - 自动发布配置

### 推荐的 Git 别名

```bash
# 添加到 ~/.gitconfig
git config --global alias.st status
git config --global alias.lg "log --oneline --graph --decorate"
git config --global alias.last "log -1 HEAD"
git config --global alias.unstage "reset HEAD --"
```

---

## ⚡ 性能提升

通过本次优化：

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 单元测试时间 | ~23秒 | 2.72秒 | **88%** |
| 集成测试时间 | ~172秒 | 67秒 | **61%** |
| 最慢测试 | 10.01秒 | 0.08秒 | **99.2%** |
| 测试总数 | - | 572 | - |
| 代码覆盖率 | - | 92% | - |

---

## 🎯 下一步（可选）

1. **配置 GitHub 仓库**
   - 设置分支保护规则
   - 配置 Secrets（PYPI_API_TOKEN, Codecov）
   - 启用 Issues 和 Discussions

2. **团队协作**
   - 添加协作者
   - 配置 CODEOWNERS
   - 设置 PR 模板

3. **增强自动化**
   - 添加 Dependabot
   - 配置自动化标签
   - 设置发布通知

4. **文档站点**
   - 使用 Sphinx 生成 API 文档
   - 部署到 GitHub Pages
   - 添加交互式示例

---

## 📞 支持

- **Git 工作流问题**: 查看 `docs/git-workflow/guide.md`
- **提交规范**: 查看 `docs/git-workflow/branch-protection.md`
- **CI/CD 问题**: 查看 `.github/workflows/` 目录
- **项目问题**: 查看 `PROJECT_STATUS.md`

---

## ✅ 验证清单

- [x] Git 仓库初始化完成
- [x] 初始提交（84个文件，18875行）
- [x] .gitignore 配置完整
- [x] GitHub Actions 工作流创建
- [x] pre-commit 钩子配置
- [x] pyproject.toml 完整配置
- [x] 分支保护策略文档
- [x] 使用指南文档
- [x] CHANGELOG.md 创建
- [x] LICENSE (MIT) 添加
- [x] 所有测试通过（572个，100%）

---

**状态**: ✅ Git 工作流配置完成，可以开始现代化开发！

**首次提交**: `e7c536d` - feat: 初始化项目并添加现代化 Git 工作流
