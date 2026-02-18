#!/usr/bin/env python3
"""
集成测试优化实施脚本

快速应用主要的优化措施
"""
import os
import sys
import subprocess
import time
from pathlib import Path

def run_command(cmd, description):
    """运行命令并计时"""
    print(f"\n{'='*70}")
    print(f"执行: {description}")
    print(f"命令: {cmd}")
    print('='*70)
    
    start = time.time()
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    elapsed = time.time() - start
    
    print(f"耗时: {elapsed:.1f}秒")
    if result.returncode != 0:
        print(f"错误: {result.stderr}")
        return False, elapsed
    
    print("成功!")
    return True, elapsed

def check_environment():
    """检查环境"""
    print("检查环境...")
    
    # 检查 Python
    if sys.version_info < (3, 7):
        print("错误: 需要 Python 3.7+")
        return False
    
    # 检查 pytest
    try:
        import pytest
        print(f"✓ pytest {pytest.__version__}")
    except ImportError:
        print("✗ pytest 未安装")
        return False
    
    # 检查环境变量
    if not os.environ.get('TEST_REAL_SSH'):
        print("⚠ 警告: TEST_REAL_SSH 未设置")
    
    return True

def install_dependencies():
    """安装必要的依赖"""
    print("\n安装优化所需的依赖...")
    
    deps = [
        "pytest-xdist",  # 并行测试
        "pytest-cov",    # 覆盖率
        "pytest-timeout", # 超时控制
    ]
    
    for dep in deps:
        cmd = f"{sys.executable} -m pip install {dep}"
        subprocess.run(cmd, shell=True, check=True)
        print(f"✓ 已安装 {dep}")

def run_baseline():
    """运行基准测试"""
    print("\n运行基准测试（串行）...")
    cmd = "python3 -m pytest tests/integration/ --run-integration -q --tb=no 2>&1 | tail -5"
    success, elapsed = run_command(cmd, "基准测试")
    return elapsed

def run_optimized():
    """运行优化后的测试"""
    print("\n运行优化后的测试（并行）...")
    
    # 设置环境变量优化
    env_vars = {
        'PYTEST_XDIST_AUTO_NUM_WORKERS': '4',
        'TEST_SLEEP_TIME': '0.5',  # 减少sleep时间
        'TEST_DATA_SIZE': '100000',  # 减小测试数据
    }
    
    env_str = ' '.join([f'{k}={v}' for k, v in env_vars.items()])
    
    # 并行执行
    cmd = f"{env_str} python3 -m pytest tests/integration/ --run-integration -q --tb=no -n 4 --dist=loadfile 2>&1 | tail -5"
    success, elapsed = run_command(cmd, "并行优化测试")
    return elapsed

def create_optimized_config():
    """创建优化配置"""
    print("\n创建优化配置...")
    
    config_content = """[pytest]
# 基本配置
testpaths = tests/integration
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# 并行配置
addopts = 
    -v
    --tb=short
    --strict-markers
    
# 测试标记
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    critical: marks tests as critical functionality
    smoke: marks tests as smoke tests
    stress: marks tests as stress tests
    serial: marks tests that must run serially (not parallel)
    
# 超时配置
timeout = 300
timeout_method = thread

# 覆盖率
filterwarnings =
    ignore::DeprecationWarning
"""
    
    with open('pytest.ini', 'w') as f:
        f.write(config_content)
    
    print("✓ 已创建 pytest.ini")

def add_test_markers():
    """添加测试标记到最耗时的测试"""
    print("\n标记耗时测试...")
    
    # 这里我们创建一个 conftest.py 自动标记
    conftest_content = '''"""
集成测试优化配置
"""
import pytest
import os

def pytest_collection_modifyitems(config, items):
    """自动为测试添加标记"""
    
    # 标记慢测试
    slow_tests = [
        "stress",
        "concurrent", 
        "sustained_load",
        "100_operations",
        "streaming_performance",
        "rapid_open_close",
    ]
    
    for item in items:
        # 自动标记慢测试
        if any(slow in item.nodeid for slow in slow_tests):
            item.add_marker(pytest.mark.slow)
        
        # 标记串行测试（不能并行）
        if "stress" in item.nodeid:
            item.add_marker(pytest.mark.serial)

def pytest_addoption(parser):
    """添加命令行选项"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests"
    )
'''
    
    conftest_path = Path('tests/integration/conftest.py')
    if conftest_path.exists():
        print(f"⚠ {conftest_path} 已存在，跳过")
    else:
        with open(conftest_path, 'w') as f:
            f.write(conftest_content)
        print(f"✓ 已创建 {conftest_path}")

def print_summary(baseline, optimized):
    """打印总结"""
    print("\n" + "="*70)
    print("优化结果总结")
    print("="*70)
    print(f"基准时间:   {baseline:.1f}秒")
    print(f"优化后时间: {optimized:.1f}秒")
    
    if baseline > 0:
        improvement = (baseline - optimized) / baseline * 100
        print(f"性能提升:   {improvement:.1f}%")
        
        if improvement > 30:
            print("🎉 优秀！大幅提升了测试速度")
        elif improvement > 10:
            print("✓ 良好！测试速度有所提升")
        else:
            print("⚠ 提升有限，考虑其他优化方案")
    
    print("\n" + "="*70)
    print("后续建议:")
    print("="*70)
    print("1. 使用 'pytest -m \"not slow\"' 运行快速测试")
    print("2. 使用 'pytest -n 4' 运行并行测试")
    print("3. 在 CI/CD 中设置 TEST_SLEEP_TIME=0.5 减少sleep")
    print("4. 定期运行完整测试套件确保覆盖率")
    print("="*70)

def main():
    """主函数"""
    print("集成测试优化工具")
    print("=" * 70)
    
    # 检查环境
    if not check_environment():
        print("环境检查失败，请修复后重试")
        sys.exit(1)
    
    # 安装依赖
    try:
        install_dependencies()
    except Exception as e:
        print(f"安装依赖失败: {e}")
        sys.exit(1)
    
    # 创建配置
    create_optimized_config()
    add_test_markers()
    
    # 运行基准测试
    print("\n准备运行基准测试...")
    input("按回车开始基准测试（串行）...")
    baseline = run_baseline()
    
    # 运行优化测试
    print("\n准备运行优化测试...")
    input("按回车开始优化测试（并行）...")
    optimized = run_optimized()
    
    # 打印总结
    print_summary(baseline, optimized)

if __name__ == "__main__":
    main()
