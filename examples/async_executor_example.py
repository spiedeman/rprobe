"""
后台任务执行示例 - tcpdump等长时间命令的非阻塞执行

示例场景：
1. 启动多个tcpdump抓包任务
2. 主线程执行其他工作
3. 检查任务状态并停止
4. 获取任务摘要（包含远程文件路径）
"""

import time
from src import SSHClient, SSHConfig


def example_basic_usage():
    """基本使用示例"""
    config = SSHConfig(
        host="your-server.com",
        username="root",
        password="your-password"
    )
    
    client = SSHClient(config)
    client.connect()
    
    try:
        # 启动tcpdump抓包（限制1000个包，会自动结束）
        task = client.bg(
            "tcpdump -i eth0 port 80 -c 1000 -w /tmp/http.pcap",
            name="http_capture"
        )
        
        print(f"任务已启动: {task.id}")
        print(f"命令: {task.command}")
        
        # 主线程做其他事
        print("主线程执行其他工作...")
        time.sleep(10)
        
        # 检查状态
        if task.is_running():
            print(f"任务运行中，已运行 {task.duration:.1f} 秒")
        elif task.is_completed():
            print("任务已完成！")
        
        # 获取摘要（轻量级，不下载文件）
        summary = task.get_summary()
        print(f"\n任务摘要:")
        print(summary)
        
        # 如果任务还在运行，停止它
        if task.is_running():
            task.stop(graceful=True, timeout=5.0)
            print("任务已停止")
    
    finally:
        client.disconnect()


def example_multiple_tasks():
    """多任务管理示例"""
    config = SSHConfig(host="your-server.com", username="root", password="your-password")
    client = SSHClient(config)
    client.connect()
    
    try:
        # 启动3个任务
        tasks = []
        
        # 任务1: 抓HTTP
        task1 = client.bg(
            "tcpdump -i eth0 port 80 -w /tmp/http.pcap",
            name="http_cap"
        )
        tasks.append(task1)
        
        # 任务2: 抓DNS
        task2 = client.bg(
            "tcpdump -i eth0 port 53 -w /tmp/dns.pcap",
            name="dns_cap"
        )
        tasks.append(task2)
        
        # 任务3: 监控日志
        task3 = client.bg(
            "tail -f /var/log/syslog",
            name="log_monitor"
        )
        tasks.append(task3)
        
        print(f"已启动 {len(client.background_tasks)} 个任务")
        
        # 主线程工作30秒
        time.sleep(30)
        
        # 批量查看状态
        print("\n任务状态汇总:")
        for task in client.background_tasks:
            summary = task.get_summary()
            print(f"  [{summary.task_id}] {summary.command[:40]}... - {summary.status}")
        
        # 通过名称查找任务
        http_task = client.get_background_task_by_name("http_cap")
        if http_task:
            print(f"\nHTTP任务状态: {http_task.status}")
        
        # 停止所有任务
        print("\n停止所有任务...")
        client.stop_all_background(graceful=True, timeout=3.0)
        
        print("\n最终摘要:")
        for task in client.background_tasks:
            summary = task.get_summary()
            print(f"  [{summary.task_id}] 时长: {summary.duration:.1f}s, 退出码: {summary.exit_code}")
    
    finally:
        client.disconnect()


def example_realtime_output():
    """实时输出查看示例"""
    config = SSHConfig(host="your-server.com", username="root", password="your-password")
    client = SSHClient(config)
    client.connect()
    
    try:
        # 启动tcpdump
        task = client.bg("tcpdump -i eth0 -n", name="packet_dump")
        
        # 实时读取输出（类似生成器）
        print("实时输出（显示最新10行）:")
        line_count = 0
        for line in task.iter_output(block=True):
            print(f"  {line}")
            line_count += 1
            if line_count >= 10:
                break
        
        # 停止任务
        task.stop()
        
        # 获取最后10行
        last_lines = task.get_summary(tail_lines=10).last_lines
        print(f"\n停止前最后10行:")
        for line in last_lines:
            print(f"  {line}")
    
    finally:
        client.disconnect()


def example_auto_cleanup():
    """自动清理示例说明"""
    """
    自动清理机制：
    1. 任务完成/停止后，会记录日志
    2. 1小时后自动从管理器清理（释放内存）
    3. 如果需要保留更久，可以调用 task.cancel_cleanup()
    
    日志输出示例：
    
    # 任务启动
    2025-02-14 10:00:00 | INFO | 后台任务已启动 [a3f7b2d] tcpdump -i eth0...
    
    # 任务自己完成（tcpdump -c 1000达到）
    2025-02-14 10:00:45 | INFO | 后台任务完成 [a3f7b2d] tcpdump -i eth0... | 退出码: 0 | 时长: 45.2s
    2025-02-14 10:00:45 | DEBUG | 任务 [a3f7b2d] 将在 3600s 后自动清理
    
    # 1小时后自动清理
    2025-02-14 11:00:45 | DEBUG | 任务 [a3f7b2d] 已从管理器自动清理
    
    # 如果被手动停止
    2025-02-14 10:05:00 | INFO | 后台任务停止 [b8e9c1a] tcpdump -i eth0... | 时长: 120.0s | 原因: 用户优雅停止
    """
    pass


if __name__ == "__main__":
    # 运行示例
    print("=== 示例1: 基本使用 ===")
    # example_basic_usage()
    
    print("\n=== 示例2: 多任务管理 ===")
    # example_multiple_tasks()
    
    print("\n=== 示例3: 实时输出 ===")
    # example_realtime_output()
    
    print("\n请根据实际环境修改配置后运行示例")
