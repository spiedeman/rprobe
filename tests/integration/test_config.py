"""
测试配置模块

集中管理测试参数，支持通过环境变量调整测试强度
"""

import os

# Sleep时间配置（秒）
# 开发环境可以设置较小的值以加速测试
SLEEP_TIME_SHORT = float(os.environ.get("TEST_SLEEP_TIME_SHORT", "0.3"))  # 原1秒
SLEEP_TIME_MEDIUM = float(os.environ.get("TEST_SLEEP_TIME_MEDIUM", "0.5"))  # 原2秒
SLEEP_TIME_LONG = float(os.environ.get("TEST_SLEEP_TIME_LONG", "3.0"))  # 原10秒

# 大数据传输配置（字节）
TEST_DATA_SMALL = int(os.environ.get("TEST_DATA_SMALL", "100000"))  # 100KB
TEST_DATA_MEDIUM = int(os.environ.get("TEST_DATA_MEDIUM", "200000"))  # 200KB，原500KB
TEST_DATA_LARGE = int(os.environ.get("TEST_DATA_LARGE", "500000"))  # 500KB，原1MB

# 并发配置
CONCURRENT_THREADS = int(os.environ.get("TEST_CONCURRENT_THREADS", "5"))  # 原10
RAPID_ITERATIONS = int(os.environ.get("TEST_RAPID_ITERATIONS", "20"))  # 原50
SUSTAINED_LOAD_DURATION = int(os.environ.get("TEST_SUSTAINED_LOAD_DURATION", "10"))  # 原30秒

# 连接池配置
POOL_MAX_CONNECTIONS = int(os.environ.get("TEST_POOL_MAX_CONNECTIONS", "5"))  # 原10


def get_test_config():
    """获取当前测试配置"""
    return {
        "sleep_times": {
            "short": SLEEP_TIME_SHORT,
            "medium": SLEEP_TIME_MEDIUM,
            "long": SLEEP_TIME_LONG,
        },
        "data_sizes": {
            "small": TEST_DATA_SMALL,
            "medium": TEST_DATA_MEDIUM,
            "large": TEST_DATA_LARGE,
        },
        "concurrent": {
            "threads": CONCURRENT_THREADS,
            "rapid_iterations": RAPID_ITERATIONS,
            "sustained_duration": SUSTAINED_LOAD_DURATION,
        },
        "pool": {
            "max_connections": POOL_MAX_CONNECTIONS,
        },
    }


def print_test_config():
    """打印当前测试配置"""
    config = get_test_config()
    print("当前测试配置:")
    print(
        f"  Sleep时间: short={config['sleep_times']['short']}s, "
        f"medium={config['sleep_times']['medium']}s, "
        f"long={config['sleep_times']['long']}s"
    )
    print(
        f"  数据大小: small={config['data_sizes']['small']/1024:.0f}KB, "
        f"medium={config['data_sizes']['medium']/1024:.0f}KB, "
        f"large={config['data_sizes']['large']/1024:.0f}KB"
    )
    print(
        f"  并发配置: threads={config['concurrent']['threads']}, "
        f"rapid_iterations={config['concurrent']['rapid_iterations']}, "
        f"sustained_duration={config['concurrent']['sustained_duration']}s"
    )
    print(f"  连接池: max_connections={config['pool']['max_connections']}")
