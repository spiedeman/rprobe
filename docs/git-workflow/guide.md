# Git 工作流使用指南

## 快速开始

### 1. 初始化开发环境

```bash
# 1. 克隆仓库（如果是新成员）
git clone <repository-url>
cd RemoteSSH

# 2. 安装依赖
pip install -r requirements.txt
pip install -e ".[dev]"

# 3. 安装 pre-commit 钩子
pre-commit install
pre-commit install --hook-type commit-msg

# 4. 验证安装
python -m pytest tests/unit -v
```

---

## 日常开发流程

### 方法一：使用 Git Worktrees（推荐）

**优点：**
- 并行开发多个功能
- 无需频繁切换分支
- 隔离不同功能的更改
- 避免隐藏文件的冲突

#### 步骤

```bash
# 1. 确保你在 main 分支且是最新的
git checkout main
git pull origin main

# 2. 创建功能分支的 worktree
git worktree add .worktrees/feature-login feature/login

# 3. 进入 worktree 目录
cd .worktrees/feature-login

# 4. 安装依赖（如果需要）
pip install -r requirements.txt

# 5. 运行测试确保基线干净
TESTING=true python -m pytest tests/unit -v

# 6. 开始开发...
# 编辑代码、编写测试、提交更改

# 7. 推送分支
git push -u origin feature/login

# 8. 创建 PR
gh pr create --title "feat: 添加登录功能" --body "实现用户认证功能"

# 9. 审查合并后清理
cd ../..
git worktree remove .worktrees/feature-login
git branch -d feature/login
```

#### 管理多个 Worktrees

```bash
# 查看所有 worktrees
git worktree list

# 示例输出：
# /Users/spiedy/RemoteSSH                main     [main]
# /Users/spiedy/RemoteSSH/.worktrees/f1  feature1 [feature1]
# /Users/spiedy/RemoteSSH/.worktrees/f2  feature2 [feature2]

# 清理已合并的 worktree
git worktree remove .worktrees/feature1

# 强制清理（如果 worktree 有未提交的更改）
git worktree remove --force .worktrees/feature1
```

### 方法二：传统分支切换（简单功能）

```bash
# 1. 更新 main 分支
git checkout main
git pull origin main

# 2. 创建并切换到功能分支
git checkout -b feature/some-feature

# 3. 开发、测试、提交
# ...

# 4. 推送并创建 PR
git push -u origin feature/some-feature
gh pr create --title "feat: xxx" --body "..."
```

---

## 提交规范实战

### 使用 Commitizen（推荐）

```bash
# 交互式创建符合规范的提交
pip install commitizen
git cz

# 或者手动提交
git commit -m "feat(pool): 添加连接池预热功能

- 实现连接预创建
- 支持配置预热数量
- 添加相关测试

Closes #123"
```

### 提交类型速查

```bash
# 新功能
git commit -m "feat: 添加SSH隧道支持"

# Bug修复
git commit -m "fix(client): 修复超时异常处理"

# 重构
git commit -m "refactor(pool): 优化连接管理逻辑"

# 测试
git commit -m "test: 添加集成测试"

# 文档
git commit -m "docs: 更新API文档"

# 性能优化
git commit -m "perf: 优化连接建立速度"
```

---

## Pull Request 流程

### 创建 PR

```bash
# 1. 推送分支
git push -u origin feature/my-feature

# 2. 使用 GitHub CLI 创建 PR
gh pr create \
  --title "feat: 添加新功能" \
  --body "## 描述

实现了 xxx 功能

## 更改

- 添加了 xxx
- 优化了 yyy
- 修复了 zzz

## 测试

- [x] 单元测试通过
- [x] 集成测试通过
- [x] 代码覆盖率 > 90%

Closes #123" \
  --base main \
  --head feature/my-feature
```

### PR 审查检查清单

在创建 PR 前自检：

```markdown
## 提交前检查

- [ ] 代码符合项目风格（Black格式化）
- [ ] 新增功能有单元测试
- [ ] 所有测试通过
- [ ] 类型注解完整
- [ ] 文档已更新
- [ ] 提交信息符合规范
- [ ] 无敏感信息泄露
- [ ] CHANGELOG已更新（如需要）
```

---

## 常见场景

### 场景1：同步主分支最新更改

```bash
# 方法1：Rebase（推荐，保持线性历史）
git checkout feature/my-feature
git fetch origin
git rebase origin/main

# 如果有冲突，解决后
git add .
git rebase --continue

# 方法2：Merge（保留分支历史）
git checkout feature/my-feature
git fetch origin
git merge origin/main
```

### 场景2：修复 PR 反馈

```bash
# 1. 修改代码
# ...

# 2. 提交更改（使用 amend 保持提交历史整洁）
git add .
git commit --amend --no-edit

# 3. 强制推送（因为是 feature 分支，可以强制推送）
git push --force-with-lease
```

### 场景3：紧急修复生产问题

```bash
# 1. 从 main 创建 hotfix 分支
git checkout main
git pull origin main
git checkout -b hotfix/critical-fix

# 2. 修复问题并提交
git commit -m "fix: 修复生产环境问题"

# 3. 创建 PR 到 main（标记为 hotfix）
gh pr create --title "hotfix: 修复关键bug" --body "..."

# 4. 紧急合并后，同步到 develop
git checkout develop
git merge main
git push origin develop
```

### 场景4：放弃当前更改

```bash
# 放弃未暂存的更改
git checkout -- <file>

# 放弃所有未暂存的更改
git checkout -- .

# 放弃已暂存但未提交的更改
git reset HEAD <file>
git checkout -- <file>

# 完全重置到上次提交（危险！）
git reset --hard HEAD
```

---

## 高级技巧

### 交互式 Rebase

```bash
# 整理最近的 5 个提交
git rebase -i HEAD~5

# 在交互式编辑器中：
# pick    - 保留提交
# reword  - 修改提交信息
# squash  - 合并到上一个提交
# fixup   - 合并到上一个提交，丢弃提交信息
# drop    - 删除提交

# 示例：合并多个提交
pick abc1234 第一个提交
squash def5678 第二个提交
squash ghi9012 第三个提交
```

### 选择性提交（Cherry-pick）

```bash
# 将某个提交应用到当前分支
git cherry-pick <commit-hash>

# 应用到多个提交
git cherry-pick abc1234 def5678
```

### Stash 暂存

```bash
# 暂存当前更改
git stash push -m "WIP: 登录功能开发中"

# 查看所有 stash
git stash list

# 应用最新的 stash
git stash pop

# 应用特定的 stash
git stash apply stash@{2}

# 删除 stash
git stash drop stash@{0}
```

### 查看历史

```bash
# 图形化历史
git log --oneline --graph --all --decorate

# 查看某个文件的更改历史
git log -p --follow -- src/core/client.py

# 查看某行代码的最后修改者
git blame src/core/client.py

# 查看提交详情
git show <commit-hash>
```

---

## 故障排除

### 问题1：推送被拒绝

```bash
# 情况1：远程有更新
# 解决：先拉取再推送
git pull origin main
git push origin main

# 情况2：分支被保护
# 解决：创建 PR，不要直接推送
```

### 问题2：合并冲突

```bash
# 1. 查看冲突文件
git status

# 2. 编辑冲突文件，解决冲突
# 冲突标记：
# <<<<<<< HEAD
# 当前分支的内容
# =======
# 要合并的内容
# >>>>>>> branch-name

# 3. 标记为已解决
git add <resolved-file>

# 4. 完成合并
git commit -m "merge: 解决合并冲突"
```

### 问题3：误删分支

```bash
# 查看引用日志
git reflog

# 找到分支的最后一次提交
git checkout -b recovered-branch <commit-hash>
```

### 问题4：大文件误提交

```bash
# 1. 从 Git 历史中移除大文件
# 安装 BFG Repo-Cleaner
brew install bfg  # macOS

# 或使用 git filter-branch
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch path/to/large-file' \
  HEAD

# 2. 强制推送（谨慎！）
git push --force-with-lease
```

---

## 工具和配置

### 推荐的 Git 配置

```bash
# 基本配置
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# 默认编辑器
git config --global core.editor "code --wait"  # VS Code
git config --global core.editor "vim"           # Vim

# 颜色输出
git config --global color.ui auto

# 合并工具
git config --global merge.tool vscode
git config --global mergetool.vscode.cmd "code --wait $MERGED"

# 默认分支名
git config --global init.defaultBranch main

# 推送策略
git config --global push.default current

# Rebase 策略
git config --global pull.rebase true
```

### 有用的别名

```bash
# 添加到 ~/.gitconfig

[alias]
    # 状态
    st = status
    s = status -s
    
    # 提交
    ci = commit
    cam = commit -am
    
    # 分支
    co = checkout
    br = branch
    
    # 日志
    lg = log --oneline --graph --decorate
    lga = log --oneline --graph --decorate --all
    last = log -1 HEAD
    
    # 撤销
    unstage = reset HEAD --
    uncommit = reset --soft HEAD^
n    discard = checkout --
    
    # PR
    pr = !gh pr create
    prc = !gh pr checkout
    prl = !gh pr list
```

### 图形化工具

- **GitKraken** - 跨平台，功能强大
- **SourceTree** - Atlassian出品，免费
- **GitHub Desktop** - 简洁易用
- **VS Code GitLens** - 集成到编辑器

---

## 最佳实践总结

1. **频繁提交** - 小步快跑，每次提交一个逻辑单元
2. **写好的提交信息** - 用 Conventional Commits 规范
3. **使用 Worktrees** - 并行开发不同功能
4. **PR 前自检** - 运行测试，检查代码质量
5. **保持分支同步** - 定期 rebase 到 main
6. **代码审查** - 所有更改都需要审查
7. **自动化** - 让 CI/CD 和 pre-commit 做检查

---

## 快速参考卡片

```
┌─────────────────────────────────────────────────────────────┐
│  初始化                                                      │
│  git init → 安装 pre-commit → 配置 user.name/email          │
├─────────────────────────────────────────────────────────────┤
│  新功能                                                      │
│  git worktree add .worktrees/f-x feature/x → cd .worktrees  │
├─────────────────────────────────────────────────────────────┤
│  日常                                                      │
│  修改 → 测试 → git add → git cz → git push → PR             │
├─────────────────────────────────────────────────────────────┤
│  同步                                                      │
│  git fetch → git rebase origin/main → git push --force      │
├─────────────────────────────────────────────────────────────┤
│  提交类型                                                    │
│  feat fix docs style refactor test chore perf ci revert     │
└─────────────────────────────────────────────────────────────┘
```
