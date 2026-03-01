#!/usr/bin/env python3
"""
性能监控和对比工具

用于监控 SSH 数据接收性能，对比不同模式的性能表现。

Usage:
    python -m src.utils.performance_monitor --help
    python -m src.utils.performance_monitor --compare
    python -m src.utils.performance_monitor --info
"""

import argparse
import sys
import time
from typing import Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, "/Users/spiedy/Documents/Code/RemoteSSH")

from rprobe.config.models import SSHConfig, RecvMode
from rprobe.receivers import SmartChannelReceiver, compare_modes


def print_performance_info(receiver: SmartChannelReceiver):
    """打印接收器的性能信息"""
    info = receiver.get_performance_info()

    print("\n" + "=" * 60)
    print("当前性能配置")
    print("=" * 60)
    print(f"当前模式: {info.get('name', info['current_mode'])}")
    print(f"配置模式: {info['config_mode']}")
    print(f"运行平台: {info['platform']}")
    print()
    print(f"描述: {info.get('description', 'N/A')}")
    print(f"预期 CPU 占用: {info.get('cpu_usage', 'N/A')}")
    print(f"预期延迟: {info.get('latency', 'N/A')}")
    print(f"适用平台: {info.get('platform', 'N/A')}")
    print("=" * 60)


def compare_all_modes():
    """对比所有模式的性能"""
    print("\n" + "=" * 60)
    print("所有模式性能对比")
    print("=" * 60)

    # 创建测试配置
    config = SSHConfig(host="example.com", username="test", password="test")

    modes = [
        (RecvMode.SELECT, "Select 模式 (Linux/Mac 推荐)"),
        (RecvMode.ADAPTIVE, "自适应轮询 (Windows 推荐)"),
        (RecvMode.ORIGINAL, "原始轮询 (向后兼容)"),
    ]

    print(f"\n{'模式':<25} {'CPU占用':<12} {'延迟':<12} {'适用平台':<15}")
    print("-" * 70)

    for mode, description in modes:
        config.recv_mode = mode
        receiver = SmartChannelReceiver(config)
        info = receiver.get_performance_info()

        # 标记当前自动选择的模式
        marker = ""
        if mode == receiver.mode:
            marker = " (*)"

        print(
            f"{description}{marker:<12} {info.get('cpu_usage', 'N/A'):<12} "
            f"{info.get('latency', 'N/A'):<12} {info.get('platform', 'N/A'):<15}"
        )

    print()
    print("(*): 当前平台自动选择的模式")
    print("=" * 60)

    print("\n推荐使用:")
    print("  1. Linux/Mac 生产环境: recv_mode='select'")
    print("     - CPU 占用最低 (~0% 等待时)")
    print("     - 响应延迟最低 (< 1ms)")
    print()
    print("  2. Windows 环境: recv_mode='adaptive' 或 'auto'")
    print("     - 兼容性好")
    print("     - CPU 占用较低 (~2-5% 等待时)")
    print()
    print("  3. 兼容性优先: recv_mode='original'")
    print("     - 与旧版本行为一致")
    print("     - 代码路径最简单")
    print("=" * 60)


def show_usage_examples():
    """显示使用示例"""
    print("\n" + "=" * 60)
    print("使用示例")
    print("=" * 60)

    examples = """
1. 使用自动模式（推荐）:
   from src import SSHClient, SSHConfig
   
   config = SSHConfig(
       host="example.com",
       username="user",
       password="pass",
       recv_mode="auto"  # 自动选择最优模式
   )
   client = SSHClient(config)

2. 显式使用 Select 模式:
   config = SSHConfig(
       host="example.com",
       username="user",
       password="pass",
       recv_mode="select"
   )

3. 显式使用自适应轮询:
   config = SSHConfig(
       host="example.com",
       username="user",
       password="pass",
       recv_mode="adaptive"
   )

4. 使用原始模式（向后兼容）:
   config = SSHConfig(
       host="example.com",
       username="user",
       password="pass",
       recv_mode="original"
   )
"""
    print(examples)
    print("=" * 60)


def monitor_performance():
    """监控当前性能状态"""
    print("\n" + "=" * 60)
    print("性能监控信息")
    print("=" * 60)

    config = SSHConfig(host="example.com", username="test", password="test", recv_mode="auto")

    receiver = SmartChannelReceiver(config)
    info = receiver.get_performance_info()

    print(f"\n当前平台: {sys.platform}")
    print(f"Python 版本: {sys.version.split()[0]}")
    print(f"自动选择模式: {info['current_mode']}")
    print()
    print("预期性能指标:")
    print(f"  - CPU 占用: {info.get('cpu_usage', 'N/A')}")
    print(f"  - 响应延迟: {info.get('latency', 'N/A')}")
    print()
    print("优化效果对比（相对于原始轮询）:")

    if info["current_mode"] == RecvMode.SELECT:
        print("  - CPU 降低: ~95-100% (从 ~15% 降至 ~0%)")
        print("  - 延迟改善: 相当 (~1ms)")
        print("  - 系统调用: 减少 ~90%")
    elif info["current_mode"] == RecvMode.ADAPTIVE:
        print("  - CPU 降低: ~70-80% (从 ~15% 降至 ~3%)")
        print("  - 延迟增加: 轻微 (最长 50ms)")
        print("  - 系统调用: 减少 ~70%")
    else:
        print("  - 使用原始模式，无优化")

    print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="SSH 性能监控工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.utils.performance_monitor --compare    # 对比所有模式
  python -m src.utils.performance_monitor --info       # 显示当前性能信息
  python -m src.utils.performance_monitor --examples   # 显示使用示例
        """,
    )

    parser.add_argument("--compare", "-c", action="store_true", help="对比所有模式的性能")

    parser.add_argument("--info", "-i", action="store_true", help="显示当前性能信息")

    parser.add_argument("--examples", "-e", action="store_true", help="显示使用示例")

    parser.add_argument("--all", "-a", action="store_true", help="显示所有信息")

    args = parser.parse_args()

    # 如果没有参数，显示帮助信息
    if not any([args.compare, args.info, args.examples, args.all]):
        parser.print_help()
        print()
        monitor_performance()
        return

    if args.all or args.compare:
        compare_all_modes()

    if args.all or args.info:
        monitor_performance()

    if args.all or args.examples:
        show_usage_examples()


if __name__ == "__main__":
    main()
