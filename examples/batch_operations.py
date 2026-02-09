#!/usr/bin/env python3
"""
批量服务器操作示例

管理多台服务器的场景
"""
import concurrent.futures
from typing import List, Dict, Tuple
from dataclasses import dataclass

from src import SSHClient, SSHConfig


@dataclass
class Server:
    """服务器配置"""
    name: str
    host: str
    username: str
    password: str


class ServerManager:
    """服务器管理器"""
    
    def __init__(self):
        self.servers: List[Server] = []
    
    def add_server(self, name: str, host: str, username: str, password: str):
        """添加服务器"""
        self.servers.append(Server(name, host, username, password))
    
    def check_all_servers(self) -> Dict[str, dict]:
        """检查所有服务器状态"""
        results = {}
        
        for server in self.servers:
            config = SSHConfig(
                host=server.host,
                username=server.username,
                password=server.password,
                timeout=10.0,
                command_timeout=10.0
            )
            
            try:
                with SSHClient(config) as client:
                    # 收集系统信息
                    info = {
                        'hostname': client.exec_command('hostname').stdout.strip(),
                        'uptime': client.exec_command('uptime').stdout.strip(),
                        'load': client.exec_command('cat /proc/loadavg').stdout.strip(),
                        'disk': client.exec_command('df -h / | tail -1').stdout.strip(),
                        'status': 'online'
                    }
                    results[server.name] = info
            except Exception as e:
                results[server.name] = {'status': 'offline', 'error': str(e)}
        
        return results
    
    def run_command_parallel(self, command: str) -> Dict[str, Tuple[int, str]]:
        """在所有服务器上并行执行命令"""
        results = {}
        
        def execute_on_server(server: Server) -> Tuple[str, int, str]:
            config = SSHConfig(
                host=server.host,
                username=server.username,
                password=server.password,
                timeout=10.0,
                command_timeout=30.0
            )
            
            try:
                with SSHClient(config, use_pool=True) as client:
                    result = client.exec_command(command)
                    return server.name, result.exit_code, result.stdout
            except Exception as e:
                return server.name, -1, str(e)
        
        # 使用线程池并行执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(execute_on_server, srv) for srv in self.servers]
            
            for future in concurrent.futures.as_completed(futures):
                name, exit_code, output = future.result()
                results[name] = (exit_code, output)
        
        return results
    
    def deploy_to_all(self, local_file: str, remote_path: str):
        """部署文件到所有服务器（概念示例）"""
        print(f"部署 {local_file} 到所有服务器的 {remote_path}")
        # 实际实现需要使用SCP或SFTP
        # 这里仅作为示例框架
        for server in self.servers:
            print(f"  - 部署到 {server.name} ({server.host})...")


def example_1_check_servers():
    """示例1: 检查所有服务器状态"""
    print("=" * 60)
    print("示例1: 检查所有服务器状态")
    print("=" * 60)
    
    manager = ServerManager()
    
    # 添加服务器（请替换为实际服务器信息）
    manager.add_server("web-01", "192.168.1.101", "admin", "password")
    manager.add_server("web-02", "192.168.1.102", "admin", "password")
    manager.add_server("db-01", "192.168.1.201", "admin", "password")
    
    results = manager.check_all_servers()
    
    for name, info in results.items():
        print(f"\n服务器: {name}")
        if info['status'] == 'online':
            print(f"  主机名: {info['hostname']}")
            print(f"  运行时间: {info['uptime']}")
            print(f"  负载: {info['load']}")
            print(f"  磁盘: {info['disk']}")
        else:
            print(f"  状态: 离线 - {info.get('error', 'Unknown')}")


def example_2_parallel_command():
    """示例2: 在所有服务器上并行执行命令"""
    print("=" * 60)
    print("示例2: 并行执行命令")
    print("=" * 60)
    
    manager = ServerManager()
    manager.add_server("server-1", "192.168.1.101", "admin", "password")
    manager.add_server("server-2", "192.168.1.102", "admin", "password")
    
    command = "whoami && date"
    results = manager.run_command_parallel(command)
    
    print(f"\n执行命令: {command}\n")
    for name, (exit_code, output) in results.items():
        status = "✓" if exit_code == 0 else "✗"
        print(f"{status} {name}:")
        print(f"   退出码: {exit_code}")
        print(f"   输出: {output[:100]}...")


def example_3_restart_service():
    """示例3: 在所有服务器上重启服务"""
    print("=" * 60)
    print("示例3: 重启服务")
    print("=" * 60)
    
    manager = ServerManager()
    manager.add_server("web-01", "192.168.1.101", "admin", "password")
    manager.add_server("web-02", "192.168.1.102", "admin", "password")
    
    # 检查服务状态
    print("\n1. 检查服务状态...")
    results = manager.run_command_parallel("systemctl is-active nginx")
    for name, (exit_code, output) in results.items():
        status = "运行中" if exit_code == 0 else "已停止"
        print(f"   {name}: {status}")
    
    # 重启服务
    print("\n2. 重启服务...")
    results = manager.run_command_parallel("sudo systemctl restart nginx")
    for name, (exit_code, output) in results.items():
        status = "成功" if exit_code == 0 else "失败"
        print(f"   {name}: {status}")
    
    # 验证重启
    print("\n3. 验证服务状态...")
    results = manager.run_command_parallel("systemctl is-active nginx")
    for name, (exit_code, output) in results.items():
        status = "✓ 运行中" if exit_code == 0 else "✗ 失败"
        print(f"   {name}: {status}")


if __name__ == "__main__":
    print("批量服务器操作示例\n")
    
    # 取消注释要运行的示例
    # example_1_check_servers()
    # example_2_parallel_command()
    # example_3_restart_service()
    
    print("\n示例完成！请根据实际服务器配置修改代码。")
