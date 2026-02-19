#!/bin/bash
# 代码质量检查脚本
# 运行所有代码质量检查

set -e

echo "🔍 运行代码质量检查..."
echo ""

# 1. 运行 black 检查
echo "1️⃣ 检查代码格式 (black)..."
python -m black src/ tests/ --check --diff || {
    echo "❌ 代码格式检查失败"
    echo "运行 'python -m black src/ tests/' 修复格式"
    exit 1
}
echo "✅ 代码格式检查通过"
echo ""

# 2. 运行 flake8 检查
echo "2️⃣ 运行代码风格检查 (flake8)..."
python -m flake8 src/ tests/ --count --statistics || {
    echo "⚠️ 发现代码风格问题（非阻塞）"
}
echo ""

# 3. 运行测试
echo "3️⃣ 运行单元测试..."
python -m pytest tests/unit -v --tb=short -q || {
    echo "❌ 测试失败"
    exit 1
}
echo "✅ 所有测试通过"
echo ""

# 4. 检查覆盖率
echo "4️⃣ 检查测试覆盖率..."
python -m pytest tests/unit --cov=src --cov-report=term-missing --cov-fail-under=70 || {
    echo "⚠️ 覆盖率低于70%"
}
echo ""

echo "🎉 代码质量检查完成!"
