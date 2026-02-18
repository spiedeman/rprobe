#!/usr/bin/env python3
"""
集成测试逐个执行监控脚本
"""
import subprocess
import sys
import time
from datetime import datetime

# 环境变量
ENV = {
    'TEST_REAL_SSH': 'true',
    'TEST_SSH_HOST': 'aliyun.spiedeman.top',
    'TEST_SSH_USER': 'admin',
    'TEST_SSH_PASS': 'bhr0204'
}

# 测试文件列表（按依赖顺序）
TEST_FILES = [
    'tests/integration/test_ssh_integration.py',      # 基础测试
    'tests/integration/test_ssh_advanced.py',         # 高级功能
    'tests/integration/test_backend_integration.py',  # 后端集成
    'tests/integration/test_pool_features.py',        # 连接池功能
    'tests/integration/test_multi_session.py',        # 多会话
    'tests/integration/test_interactive.py',          # 交互式
    'tests/integration/test_error_recovery.py',       # 错误恢复
    'tests/integration/test_blackbox_coverage.py',    # 黑盒覆盖
    'tests/integration/test_whitebox_coverage.py',    # 白盒覆盖
    'tests/integration/test_supplemental.py',         # 补充测试
    'tests/integration/test_stress.py',               # 压力测试
]

def run_test(test_file):
    """运行单个测试文件"""
    print(f"\n{'='*70}")
    print(f"运行: {test_file}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*70)
    
    start_time = time.time()
    
    cmd = [
        'python3', '-m', 'pytest',
        test_file,
        '-v',
        '--run-integration',
        '--tb=short'
    ]
    
    env = {**ENV}
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5分钟超时
            env=env
        )
        
        elapsed = time.time() - start_time
        
        # 输出结果
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # 解析结果
        passed = result.returncode == 0
        
        if passed:
            print(f"✅ 通过 ({elapsed:.1f}s)")
        else:
            print(f"❌ 失败 ({elapsed:.1f}s)")
        
        return passed, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        print(f"⏱️ 超时 (>300s)")
        return False, "", "Timeout"
    except Exception as e:
        print(f"💥 错误: {e}")
        return False, "", str(e)

def main():
    """主函数"""
    print("开始逐个执行集成测试...")
    print(f"环境: {ENV['TEST_SSH_HOST']}")
    
    results = {}
    failed_tests = []
    
    for test_file in TEST_FILES:
        passed, stdout, stderr = run_test(test_file)
        results[test_file] = {
            'passed': passed,
            'stdout': stdout,
            'stderr': stderr
        }
        
        if not passed:
            failed_tests.append(test_file)
            print(f"\n⚠️ {test_file} 失败，需要修复")
            # 继续下一个，不停止
    
    # 汇总
    print(f"\n{'='*70}")
    print("测试汇总")
    print('='*70)
    
    total = len(TEST_FILES)
    passed_count = sum(1 for r in results.values() if r['passed'])
    failed_count = total - passed_count
    
    print(f"总计: {total} 个测试文件")
    print(f"通过: {passed_count}")
    print(f"失败: {failed_count}")
    
    if failed_tests:
        print(f"\n失败的测试:")
        for t in failed_tests:
            print(f"  - {t}")
    
    return failed_count == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
