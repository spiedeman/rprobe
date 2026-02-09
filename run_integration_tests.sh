#!/bin/bash
# 运行所有集成测试的脚本

echo "=================================="
echo "RemoteSSH 集成测试运行脚本"
echo "=================================="
echo ""

# 设置环境变量
export TESTING=true
export TEST_REAL_SSH=true
export TEST_SSH_HOST=debian13.local
export TEST_SSH_USER=spiedy
export TEST_SSH_PASS=bhr0204

echo "测试服务器: $TEST_SSH_HOST"
echo "测试用户: $TEST_SSH_USER"
echo ""

# 运行基础集成测试
echo "1. 运行基础集成测试..."
python -m pytest tests/integration/test_ssh_integration.py --run-integration -v --tb=short 2>&1 | tail -5
echo ""

# 运行高级集成测试
echo "2. 运行高级集成测试..."
python -m pytest tests/integration/test_ssh_advanced.py --run-integration -v --tb=short 2>&1 | tail -10
echo ""

# 运行压力测试
echo "3. 运行压力测试（部分）..."
python -m pytest tests/integration/test_stress.py::TestConnectionPoolStress --run-integration -v --tb=short 2>&1 | tail -5
echo ""

echo "=================================="
echo "集成测试运行完成！"
echo "=================================="
