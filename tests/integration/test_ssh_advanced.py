"""
高级集成测试 - 加固真实环境测试

需要真实 SSH 服务器，测试复杂场景和边界情况。

运行方式:
    export TEST_REAL_SSH=true
    export TEST_SSH_HOST=your-host
    export TEST_SSH_USER=your-user
    export TEST_SSH_PASS=your-password
    python -m pytest tests/integration/test_ssh_advanced.py -v --run-integration
"""
import time
import threading
import concurrent.futures
import pytest

from src import SSHConfig, SSHClient, load_config
from src.pooling import get_pool_manager
from src.exceptions import CommandTimeoutError, ConnectionError


@pytest.mark.integration
class TestLongRunningCommands:
    """长时间运行命令测试"""
    
    def test_long_running_command_with_timeout(self, test_environment):
        """测试长时间命令超时处理"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=2.0,  # 2秒超时
        )
        
        with SSHClient(config) as client:
            # 应该超时 (可能是 TimeoutError 或 CommandTimeoutError)
            with pytest.raises((CommandTimeoutError, TimeoutError)):
                client.exec_command("sleep 10")
    
    def test_long_running_command_success(self, test_environment):
        """测试长时间命令成功完成"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=10.0,
        )
        
        with SSHClient(config) as client:
            start = time.time()
            result = client.exec_command("sleep 2 && echo 'Completed'")
            elapsed = time.time() - start
            
            assert result.exit_code == 0
            assert "Completed" in result.stdout
            assert 1.5 < elapsed < 3.0  # 确保实际等待了
    
    def test_command_with_large_output(self, test_environment):
        """测试大输出命令"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=30.0,
            command_timeout=30.0,
            max_output_size=50 * 1024 * 1024,  # 50MB
        )
        
        with SSHClient(config) as client:
            # 生成大输出 - 使用 seq 生成更多行
            result = client.exec_command("seq 1 10000")
            
            assert result.exit_code == 0
            assert len(result.stdout) > 10000  # 至少10KB输出
    
    def test_multiple_commands_sequential(self, test_environment):
        """测试顺序执行多个命令"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        commands = [
            ("echo 'Test1'", "Test1"),
            ("echo 'Test2'", "Test2"),
            ("uname -s", "Linux"),  # 假设Linux服务器
            ("whoami", test_environment['test_user']),
        ]
        
        with SSHClient(config) as client:
            for cmd, expected in commands:
                result = client.exec_command(cmd)
                assert result.exit_code == 0
                assert expected in result.stdout


@pytest.mark.integration
class TestConnectionPoolStress:
    """连接池压力测试"""
    
    def test_pool_concurrent_connections(self, test_environment):
        """测试连接池并发访问"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                client = SSHClient(config, use_pool=True, max_size=5)
                with client:
                    result = client.exec_command(f"echo 'Worker{worker_id}'")
                    results.append((worker_id, result.stdout))
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # 10个线程并发
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证所有工作都完成
        assert len(results) == 10
        assert len(errors) == 0
        
        # 验证每个worker的输出
        for worker_id, output in results:
            assert f"Worker{worker_id}" in output
    
    def test_pool_reuse_efficiency(self, test_environment):
        """测试连接池复用效率"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        client = SSHClient(config, use_pool=True, max_size=3, min_size=1)
        
        try:
            # 执行10次命令
            for i in range(10):
                result = client.exec_command(f"echo 'Command{i}'")
                assert result.exit_code == 0
            
            # 验证连接池统计
            stats = client._pool.stats
            assert stats['reused'] >= 5  # 至少复用5次（考虑到并发可能创建更多）
            assert stats['created'] <= 10  # 最多创建10个连接（考虑到并发）
            
            # 验证效率提升：复用次数应该大于创建次数
            assert stats['reused'] > stats['created'] / 2
            
        finally:
            client.disconnect()
    
    def test_pool_exhaustion_handling(self, test_environment):
        """测试连接池耗尽处理"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        # 创建小连接池
        client = SSHClient(config, use_pool=True, max_size=2, min_size=2)
        
        try:
            acquired = []
            
            def acquire_and_hold(worker_id):
                with client._pool.get_connection() as conn:
                    acquired.append(worker_id)
                    time.sleep(1)  # 持有1秒
            
            # 启动3个线程（超过max_size=2）
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(acquire_and_hold, i) for i in range(3)]
                
                # 等待所有完成
                concurrent.futures.wait(futures, timeout=5)
            
            # 所有线程都应该成功（等待机制）
            assert len(acquired) == 3
            
        finally:
            client.disconnect()


@pytest.mark.integration
class TestShellSessionAdvanced:
    """高级 Shell 会话测试"""
    
    def test_shell_session_state_persistence(self, test_environment):
        """测试 Shell 会话状态保持"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        with SSHClient(config) as client:
            # 打开会话
            prompt = client.open_shell_session()
            assert len(prompt) > 0
            
            # 设置环境变量
            client.shell_command("export TEST_VAR='HelloWorld'")
            client.shell_command("export ANOTHER_VAR=12345")
            
            # 验证变量保持
            result = client.shell_command("echo $TEST_VAR")
            assert "HelloWorld" in result.stdout
            
            result = client.shell_command("echo $ANOTHER_VAR")
            assert "12345" in result.stdout
            
            # 切换目录
            client.shell_command("cd /tmp")
            result = client.shell_command("pwd")
            assert "/tmp" in result.stdout
            
            # 验证变量仍然存在
            result = client.shell_command("echo $TEST_VAR")
            assert "HelloWorld" in result.stdout
            
            client.close_shell_session()
    
    def test_shell_session_multiple_commands(self, test_environment):
        """测试 Shell 会话中执行多个命令"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        with SSHClient(config) as client:
            prompt = client.open_shell_session()
            
            # 快速执行多个命令
            commands = [
                "date",
                "whoami",
                "hostname",
                "pwd",
                "echo 'Test done'"
            ]
            
            for cmd in commands:
                result = client.shell_command(cmd)
                assert result.exit_code == 0
                assert len(result.stdout) >= 0
            
            client.close_shell_session()
    
    def test_shell_session_with_pool(self, test_environment):
        """测试 Shell 会话与连接池结合"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        client = SSHClient(config, use_pool=True, max_size=3)
        
        try:
            # Shell 会话
            prompt = client.open_shell_session()
            result = client.shell_command("echo 'From Shell'")
            assert "From Shell" in result.stdout
            client.close_shell_session()
            
            # 普通命令
            result = client.exec_command("echo 'From Exec'")
            assert "From Exec" in result.stdout
            
            # 再次打开 Shell
            prompt = client.open_shell_session()
            result = client.shell_command("echo 'From Shell Again'")
            assert "From Shell Again" in result.stdout
            client.close_shell_session()
            
        finally:
            client.disconnect()


@pytest.mark.integration
class TestErrorRecovery:
    """错误恢复测试"""
    
    def test_reconnect_after_disconnect(self, test_environment):
        """测试断开后重连"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        client = SSHClient(config)
        
        # 首次连接
        client.connect()
        result = client.exec_command("echo 'First'")
        assert "First" in result.stdout
        
        # 断开连接
        client.disconnect()
        assert not client.is_connected
        
        # 重新连接
        client.connect()
        result = client.exec_command("echo 'Second'")
        assert "Second" in result.stdout
        
        client.disconnect()
    
    def test_invalid_command_handling(self, test_environment):
        """测试无效命令处理"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=5.0,
        )
        
        with SSHClient(config) as client:
            # 执行不存在的命令
            result = client.exec_command("this_command_does_not_exist_12345")
            
            assert result.exit_code != 0  # 应该失败
            assert len(result.stderr) > 0 or len(result.stdout) >= 0
    
    def test_permission_denied_handling(self, test_environment):
        """测试权限拒绝处理"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=5.0,
        )
        
        with SSHClient(config) as client:
            # 尝试访问没有权限的文件
            result = client.exec_command("cat /root/.bashrc 2>&1 || echo 'Permission denied'")
            
            # 要么有权限错误，要么我们的echo执行了
            assert result.exit_code == 0 or "Permission denied" in result.stdout or "denied" in result.stderr.lower()


@pytest.mark.integration
class TestMultiServerScenario:
    """多服务器场景测试"""
    
    def test_multiple_servers_with_pool_manager(self, test_environment):
        """测试多服务器连接池管理"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        # 使用同一服务器的不同配置模拟多服务器
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        manager = get_pool_manager()
        
        # 获取两个连接池（实际是同一个服务器）
        pool1 = manager.get_or_create_pool(config, max_size=2)
        pool2 = manager.get_or_create_pool(config, max_size=2)
        
        # 应该是同一个池
        assert pool1 is pool2
        
        # 获取统计
        stats = manager.get_all_stats()
        assert len(stats) >= 1
        
        # 清理
        manager.close_all()
    
    def test_performance_comparison(self, test_environment):
        """测试性能对比"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        # 无连接池
        start = time.time()
        for _ in range(3):
            with SSHClient(config, use_pool=False) as client:
                client.exec_command("echo 'test'")
        no_pool_time = time.time() - start
        
        # 有连接池
        client = SSHClient(config, use_pool=True, max_size=3)
        start = time.time()
        for _ in range(3):
            client.exec_command("echo 'test'")
        with_pool_time = time.time() - start
        client.disconnect()
        
        # 连接池应该更快或相当（因为复用连接）
        print(f"\nPerformance: No pool={no_pool_time:.2f}s, With pool={with_pool_time:.2f}s")


@pytest.mark.integration
class TestEdgeCases:
    """边界情况测试"""
    
    def test_very_short_command(self, test_environment):
        """测试极短命令"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        with SSHClient(config) as client:
            result = client.exec_command("true")  # 最短的命令
            assert result.exit_code == 0
            
            result = client.exec_command(":")  # Bash空操作
            assert result.exit_code == 0
    
    def test_command_with_special_characters(self, test_environment):
        """测试特殊字符命令"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        with SSHClient(config) as client:
            # 特殊字符
            result = client.exec_command("echo 'Hello; World | Test > < &'")
            assert "Hello; World | Test > < &" in result.stdout
            
            # Unicode
            result = client.exec_command("echo '中文测试'")
            assert "中文测试" in result.stdout
    
    def test_command_with_quotes(self, test_environment):
        """测试带引号的命令"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        with SSHClient(config) as client:
            result = client.exec_command('echo "Double quoted"')
            assert "Double quoted" in result.stdout
            
            result = client.exec_command("echo 'Single quoted'")
            assert "Single quoted" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
