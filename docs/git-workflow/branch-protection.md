# Git 分支保护策略

## 分支模型：GitHub Flow（简化版）

### 分支说明

| 分支 | 用途 | 保护级别 | 合并要求 |
|------|------|----------|----------|
| `main` | 生产就绪代码 | 🔴 严格保护 | PR + 审查 + CI通过 |
| `develop` | 集成开发 | 🟡 中等保护 | PR + CI通过 |
| `feature/*` | 功能开发 | 🟢 无保护 | 直接推送 |
| `hotfix/*` | 紧急修复 | 🟢 无保护 | PR到main |
| `release/*` | 版本发布 | 🟡 中等保护 | PR + 审查 |

---

## GitHub 分支保护规则配置

### 1. `main` 分支保护（严格）

在 GitHub 仓库设置中配置：

```yaml
Settings → Branches → Add rule for "main"

✅ Require a pull request before merging
   - Require approvals: 1
   - Dismiss stale PR approvals when new commits are pushed
   - Require review from CODEOWNERS

✅ Require status checks to pass before merging
   - Require branches to be up to date before merging
   - Status checks:
     - test (3.9)
     - test (3.10)
     - test (3.11)
     - test (3.12)
     - code-quality

✅ Require conversation resolution before merging

✅ Require signed commits (推荐)

✅ Include administrators (管理员也需要遵守)

✅ Restrict pushes that create files larger than 100MB

❌ Allow force pushes (禁止强制推送)

❌ Allow deletions (禁止删除)
```

### 2. `develop` 分支保护（中等）

```yaml
Settings → Branches → Add rule for "develop"

✅ Require a pull request before merging
   - Require approvals: 1

✅ Require status checks to pass before merging
   - test (3.11)
   - code-quality

❌ Allow force pushes

❌ Allow deletions
```

---

## 提交信息规范（Conventional Commits）

### 格式
```
<type>(<scope>): <subject>

<body>

<footer>
```

### 类型说明

| 类型 | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(pool): 添加连接池预热功能` |
| `fix` | 修复bug | `fix(client): 修复超时处理逻辑` |
| `docs` | 文档更新 | `docs(readme): 更新安装说明` |
| `style` | 代码格式 | `style: 格式化代码，无功能变化` |
| `refactor` | 重构 | `refactor(connection): 优化连接管理` |
| `test` | 测试相关 | `test(pool): 添加连接池压力测试` |
| `chore` | 构建/工具 | `chore(deps): 更新依赖版本` |
| `perf` | 性能优化 | `perf(receiver): 优化数据接收速度` |
| `ci` | CI/CD变更 | `ci(github): 添加自动发布工作流` |
| `revert` | 回滚 | `revert: 回滚上次提交` |

### 范围（Scope）建议

- `client` - SSHClient 相关
- `pool` - 连接池相关
- `config` - 配置管理相关
- `receiver` - 数据接收器相关
- `session` - Shell会话相关
- `test` - 测试相关
- `docs` - 文档相关
- `ci` - CI/CD相关

### 提交示例

```bash
# 功能提交
git commit -m "feat(pool): 添加连接池并行创建功能

- 使用 ThreadPoolExecutor 实现并行连接
- 性能提升：4.8倍
- 支持配置最大并行数

Closes #123"

# 修复提交
git commit -m "fix(client): 修复Shell会话超时问题

- 将默认超时从10秒减少到0.01秒（测试环境）
- 修复测试失败问题

Fixes #456"

# 文档提交
git commit -m "docs: 更新Git工作流文档

- 添加分支保护策略说明
- 添加提交规范示例"
```

---

## 代码审查（Code Review）规范

### 审查清单

#### 功能性
- [ ] 代码是否实现了需求？
- [ ] 边界情况是否处理？
- [ ] 错误处理是否完善？
- [ ] 测试是否覆盖新功能？

#### 代码质量
- [ ] 代码是否符合PEP 8规范？
- [ ] 是否有适当的类型注解？
- [ ] 函数/类/变量命名是否清晰？
- [ ] 复杂逻辑是否有注释？

#### 测试
- [ ] 单元测试是否通过？
- [ ] 新增代码是否有测试覆盖？
- [ ] 测试是否清晰可读？

#### 性能
- [ ] 是否有性能瓶颈？
- [ ] 资源使用是否合理？

#### 安全
- [ ] 是否有敏感信息泄露？
- [ ] 输入验证是否充分？

### 审查评论规范

```
# 使用标签明确评论类型

[Nitpick] - 小问题，非阻塞
[Question] - 疑问，需要澄清
[Suggestion] - 建议，可选采纳
[Blocking] - 阻塞性问题，必须修复
[Discussion] - 需要讨论

# 示例
[Suggestion] 考虑使用更描述性的变量名
[Question] 这个方法是否线程安全？
[Blocking] 缺少错误处理逻辑
```

---

## 版本发布流程

### 版本号规则（SemVer）

```
主版本号.次版本号.修订号
1.2.3
```

- **主版本号**：不兼容的API更改
- **次版本号**：向后兼容的功能添加
- **修订号**：向后兼容的问题修复

### 发布步骤

1. **准备发布分支**
   ```bash
   git checkout -b release/v1.2.0
   ```

2. **更新版本号**
   - 更新 `pyproject.toml`
   - 更新 `src/__init__.py`

3. **更新 CHANGELOG.md**

4. **创建 PR 到 main**

5. **合并后自动发布**
   - GitHub Actions 自动创建 Tag
   - 自动生成 Release Notes
   - 自动发布到 PyPI（配置后）

---

## 紧急修复流程（Hotfix）

```bash
# 1. 从 main 创建 hotfix 分支
git checkout main
git pull origin main
git checkout -b hotfix/fix-critical-bug

# 2. 修复问题并提交
git commit -m "fix: 修复关键bug描述"

# 3. 创建 PR 到 main（高优先级审查）

# 4. 合并后同步到 develop
git checkout develop
git merge main
```

---

## Git Worktrees 使用建议

### 推荐工作流

```bash
# 安装 pre-commit 钩子后，创建功能分支的 worktree
# 详见 git-workflow-guide.md

# 示例：同时开发多个功能
git worktree add .worktrees/feature-auth feature/auth
git worktree add .worktrees/feature-cache feature/cache
git worktree add .worktrees/bugfix-timeout bugfix/timeout

# 每个 worktree 都是独立的工作空间
# 可以在不同目录同时工作，无需切换分支
```

---

## 自动化检查

### 预提交钩子（本地）
- 代码格式化（Black）
- 导入排序（isort）
- 代码检查（flake8）
- 安全检查（bandit）
- 提交信息检查（commitizen）

### CI/CD 检查（云端）
- 多版本 Python 测试
- 代码覆盖率检查
- 类型检查（mypy）
- 代码质量检查

---

## 配置快速参考

### 必需的环境变量

```bash
# Git 配置
git config user.name "Your Name"
git config user.email "your.email@example.com"

# GitHub CLI（可选）
gh auth login

# 安装 pre-commit
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
```

### 推荐的 Git 别名

```bash
git config --global alias.st status
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.ci commit
git config --global alias.lg "log --oneline --graph --decorate"
git config --global alias.last "log -1 HEAD"
git config --global alias.unstage "reset HEAD --"
git config --global alias.visual "!gitk"
```
