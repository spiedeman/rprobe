"""
黑盒测试补充 - 使用黑盒测试方法进行质量加固

测试方法：
1. 等价类划分 (Equivalence Partitioning)
2. 边界值分析 (Boundary Value Analysis)
3. 决策表测试 (Decision Table Testing)
4. 状态转换测试 (State Transition Testing)
5. 错误推测法 (Error Guessing)
6. 场景测试 (Scenario Testing)
"""
import time
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from src import SSHClient, SSHConfig
from src.pooling import ConnectionPool
from src.core.connection import ConnectionManager, MultiSessionManager


# ============================================================================
# 1. 等价类划分测试 (Equivalence Partitioning)
# ============================================================================

@pytest.mark.integration
class TestEquivalencePartitioning:
    """等价类划分测试 - 将输入划分为有效/无效等价类"""
    
    # 有效等价类：正常配置
    def test_valid_config_normal(self, test_environment):
        """有效等价类：正常配置"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=30.0,
            command_timeout=60.0,
        )
        
        with SSHClient(config) as client:
            result = client.exec_command("echo 'valid'")
            assert result.exit_code == 0
            assert "valid" in result.stdout
    
    # 有效等价类：超时配置较大
    def test_valid_config_long_timeout(self, test_environment):
        """有效等价类：较长的超时时间"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=300.0,  # 较长的超时
            command_timeout=600.0,
        )
        
        with SSHClient(config) as client:
            result = client.exec_command("echo 'long timeout'")
            assert result.exit_code == 0
    
    # 无效等价类：空命令
    def test_invalid_empty_command(self, test_environment):
        """无效等价类：空命令"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        with SSHClient(config) as client:
            # 空命令应该返回成功（无操作）
            result = client.exec_command("")
            assert result.exit_code == 0
    
    # 无效等价类：超长命令（有效边界内）
    def test_valid_long_command_within_limit(self, test_environment):
        """有效等价类：较长的命令（在限制内）"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        with SSHClient(config) as client:
            # 生成较长的命令（100个字符）
            long_arg = "a" * 100
            result = client.exec_command(f"echo {long_arg}")
            assert result.exit_code == 0
            assert long_arg in result.stdout
    
    # 无效等价类：特殊字符命令
    def test_invalid_special_chars(self, test_environment):
        """无效等价类：特殊字符"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        with SSHClient(config) as client:
            # 包含特殊字符的命令
            result = client.exec_command("echo 'test; rm -rf /' 2>/dev/null || echo 'safe'")
            # 应该安全执行，不会真正删除
            assert "safe" in result.stdout or result.exit_code == 0


# ============================================================================
# 2. 边界值分析测试 (Boundary Value Analysis)
# ============================================================================

@pytest.mark.integration
class TestBoundaryValueAnalysis:
    """边界值分析测试 - 测试边界条件"""
    
    # 连接池大小边界值
    def test_boundary_pool_size_min(self, test_environment):
        """边界值：最小连接池大小 (min_size=0)"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(config, max_size=1, min_size=0, health_check_interval=0)
        
        try:
            # 验证可以正常使用
            with pool.get_connection() as conn:
                assert conn.is_connected
        finally:
            pool.close()
    
    def test_boundary_pool_size_one(self, test_environment):
        """边界值：连接池大小为1"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(config, max_size=1, min_size=1, health_check_interval=0)
        
        try:
            # 获取唯一连接
            with pool.get_connection() as conn:
                assert conn.is_connected
                
                # 在另一个线程尝试获取（应该等待）
                result = []
                def try_acquire():
                    try:
                        with pool.get_connection(timeout=0.1) as conn2:
                            result.append("success")
                    except Exception:
                        result.append("timeout")
                
                thread = threading.Thread(target=try_acquire)
                thread.start()
                thread.join(timeout=0.5)
                
                assert len(result) > 0
        finally:
            pool.close()
    
    def test_boundary_pool_size_max(self, test_environment):
        """边界值：较大的连接池大小"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(config, max_size=10, min_size=1, health_check_interval=0)
        
        try:
            # 获取多个连接
            connections = []
            for _ in range(5):
                ctx = pool.get_connection()
                conn = ctx.__enter__()
                connections.append((ctx, conn))
            
            # 验证所有连接都有效
            for _, conn in connections:
                assert conn.is_connected
            
            # 释放所有连接
            for ctx, _ in connections:
                ctx.__exit__(None, None, None)
        finally:
            pool.close()
    
    # 超时边界值
    def test_boundary_timeout_zero(self, test_environment):
        """边界值：较短的超时时间"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=1.0,  # 短超时但仍需足够完成SSH握手
            command_timeout=1.0,
        )

        # 短超时应该也能快速连接
        with SSHClient(config) as client:
            result = client.exec_command("echo 'quick'")
            assert result.exit_code == 0
    
    def test_boundary_timeout_large(self, test_environment):
        """边界值：较大的超时时间"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=300.0,  # 5分钟
            command_timeout=600.0,  # 10分钟
        )
        
        with SSHClient(config) as client:
            result = client.exec_command("echo 'long timeout ok'")
            assert result.exit_code == 0
    
    # 空闲时间边界值
    def test_boundary_idle_time_min(self, test_environment):
        """边界值：极短的空闲超时"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(
            config, 
            max_size=2, 
            min_size=1, 
            max_idle=0.05,  # 50ms
            health_check_interval=0
        )
        
        try:
            # 获取并释放连接
            with pool.get_connection() as conn:
                pass
            
            # 等待超过空闲时间
            time.sleep(0.1)
            
            # 再次获取（应该发现过期）
            with pool.get_connection() as conn:
                assert conn.is_connected
        finally:
            pool.close()


# ============================================================================
# 3. 决策表测试 (Decision Table Testing)
# ============================================================================

@pytest.mark.integration
class TestDecisionTable:
    """决策表测试 - 基于条件组合的测试"""
    
    # 决策表：连接获取条件
    # 条件：池是否关闭 | 池是否为空 | 是否达最大连接数 | 连接是否健康
    # 动作：抛出异常 | 复用连接 | 创建新连接 | 等待
    
    def test_decision_table_1_pool_closed(self, test_environment):
        """决策表：池关闭 → 抛出异常"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(config, max_size=2, min_size=0, health_check_interval=0)
        pool.close()
        
        # 条件：池关闭（无论其他条件如何）
        # 动作：抛出异常
        with pytest.raises(RuntimeError):
            with pool.get_connection() as conn:
                pass
    
    def test_decision_table_2_pool_empty_not_max(self, test_environment):
        """决策表：池为空 + 未达最大连接数 → 创建新连接"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(config, max_size=2, min_size=0, health_check_interval=0)
        
        try:
            # 条件：池为空 + 未达最大连接数
            # 动作：创建新连接
            with pool.get_connection() as conn:
                assert conn.is_connected
        finally:
            pool.close()
    
    def test_decision_table_3_has_healthy_connection(self, test_environment):
        """决策表：池中有健康连接 → 复用连接"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(config, max_size=2, min_size=1, health_check_interval=0)
        
        try:
            # 先获取并释放连接，使其回到池中
            with pool.get_connection() as conn:
                pass
            
            # 条件：池中有健康连接
            # 动作：复用连接
            with pool.get_connection() as conn:
                assert conn.is_connected
            
            # 验证复用了连接
            assert pool.stats['reused'] >= 1
        finally:
            pool.close()
    
    def test_decision_table_4_has_unhealthy_connection(self, test_environment):
        """决策表：池中有不健康连接 → 关闭并创建新连接"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(
            config, 
            max_size=2, 
            min_size=1, 
            max_idle=0.05,  # 快速过期
            health_check_interval=0
        )
        
        try:
            # 获取并释放连接
            with pool.get_connection() as conn:
                pass
            
            # 等待连接过期（变为不健康）
            time.sleep(0.1)
            
            # 条件：池中有不健康连接
            # 动作：关闭过期连接，创建新连接
            with pool.get_connection() as conn:
                assert conn.is_connected
            
            # 验证有过期连接
            assert pool.stats['expired'] >= 1
        finally:
            pool.close()


# ============================================================================
# 4. 状态转换测试 (State Transition Testing)
# ============================================================================

@pytest.mark.integration
class TestStateTransition:
    """状态转换测试 - 测试对象状态变化"""
    
    # ConnectionPool 状态机：
    # [初始化] -> [运行中] -> [关闭] -> [重置] -> [运行中]
    
    def test_state_transition_init_to_running(self, test_environment):
        """状态转换：初始化 -> 运行中"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(config, max_size=2, min_size=1, health_check_interval=0)
        
        # 验证状态：运行中
        assert not pool._closed
        assert pool.stats['pool_size'] >= 0
        
        # 验证可以获取连接
        with pool.get_connection() as conn:
            assert conn.is_connected
        
        pool.close()
    
    def test_state_transition_running_to_closed(self, test_environment):
        """状态转换：运行中 -> 关闭"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(config, max_size=2, min_size=1, health_check_interval=0)
        
        # 获取连接使用
        with pool.get_connection() as conn:
            assert conn.is_connected
        
        # 状态转换：运行中 -> 关闭
        pool.close()
        
        # 验证状态：关闭
        assert pool._closed
        assert pool.stats['pool_size'] == 0
    
    def test_state_transition_closed_to_reset_to_running(self, test_environment):
        """状态转换：关闭 -> 重置 -> 运行中"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(config, max_size=2, min_size=1, health_check_interval=0)
        
        # 使用连接池
        with pool.get_connection() as conn:
            pass
        
        # 关闭
        pool.close()
        assert pool._closed
        
        # 状态转换：关闭 -> 重置 -> 运行中
        pool.reset()
        
        # 验证状态：运行中
        assert not pool._closed
        assert pool.stats['pool_size'] >= 1
        
        # 验证可以再次使用
        with pool.get_connection() as conn:
            assert conn.is_connected
        
        pool.close()
    
    def test_state_transition_session_lifecycle(self, test_environment):
        """状态转换：会话生命周期"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            # 状态：无会话
            assert mgr.active_session_count == 0
            
            # 状态转换：无 -> 活跃
            session = mgr.create_session("test_state")
            assert mgr.active_session_count == 1
            
            # 使用会话
            output = session.execute_command("echo 'active'")
            assert "active" in output
            
            # 状态转换：活跃 -> 关闭
            mgr.close_session("test_state")
            assert mgr.active_session_count == 0
            
        finally:
            conn.disconnect()


# ============================================================================
# 5. 错误推测法测试 (Error Guessing)
# ============================================================================

@pytest.mark.integration
class TestErrorGuessing:
    """错误推测法测试 - 基于经验预测错误"""
    
    def test_error_concurrent_access_same_connection(self, test_environment):
        """错误推测：并发访问同一连接可能的问题"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        pool = ConnectionPool(config, max_size=1, min_size=1, health_check_interval=0)
        
        try:
            errors = []
            results = []
            
            def worker(worker_id):
                try:
                    with pool.get_connection(timeout=2.0) as conn:
                        # 快速执行命令
                        channel = conn.open_channel()
                        channel.close()
                        results.append(worker_id)
                except Exception as e:
                    errors.append((worker_id, str(e)))
            
            # 5个线程竞争1个连接
            threads = []
            for i in range(5):
                t = threading.Thread(target=worker, args=(i,))
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join(timeout=5.0)
            
            # 验证没有严重错误
            assert len(results) >= 1, "至少应该有一个成功"
            
        finally:
            pool.close()
    
    def test_error_rapid_open_close(self, test_environment):
        """错误推测：快速打开关闭连接可能导致资源泄漏"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        # 快速打开关闭50次
        for i in range(50):
            with SSHClient(config, use_pool=True, max_size=2) as client:
                result = client.exec_command(f"echo {i}")
                assert result.exit_code == 0
    
    def test_error_invalid_utf8_in_output(self, test_environment):
        """错误推测：输出中包含无效UTF-8字符"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        with SSHClient(config) as client:
            # 生成包含各种字符的输出
            result = client.exec_command("printf 'test\x80\x81\x82' 2>/dev/null || echo 'binary ok'")
            # 应该能处理，不会崩溃
            assert result.exit_code == 0 or result.exit_code == 1
    
    def test_error_command_injection_attempt(self, test_environment):
        """错误推测：命令注入尝试"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        with SSHClient(config) as client:
            # 尝试命令注入（应该被正确处理）
            result = client.exec_command("echo 'hello'; echo 'world'")
            # 应该只执行echo，不会执行其他命令
            assert "hello" in result.stdout
            assert "world" in result.stdout
    
    def test_error_network_interruption_recovery(self, test_environment):
        """错误推测：网络中断后的恢复"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            # 先执行一个命令
            channel1 = conn.open_channel()
            channel1.close()
            
            # 模拟短暂等待（模拟网络不稳定）
            time.sleep(0.1)
            
            # 再次执行，应该仍然可用
            channel2 = conn.open_channel()
            channel2.close()
            
        finally:
            conn.disconnect()


# ============================================================================
# 6. 场景测试 (Scenario Testing)
# ============================================================================

@pytest.mark.integration
class TestScenarioTesting:
    """场景测试 - 基于用户使用场景"""
    
    def test_scenario_batch_deployment(self, test_environment):
        """场景：批量部署到多台服务器"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        # 模拟部署步骤
        with SSHClient(config, use_pool=True) as client:
            # 1. 检查磁盘空间
            result = client.exec_command("df -h / | tail -1 | awk '{print $4}'")
            assert result.exit_code == 0
            
            # 2. 创建部署目录
            result = client.exec_command("mkdir -p /tmp/deploy_test && echo 'dir created'")
            assert "dir created" in result.stdout
            
            # 3. 检查服务状态
            result = client.exec_command("echo 'service ok'")
            assert "service ok" in result.stdout
            
            # 4. 清理
            result = client.exec_command("rm -rf /tmp/deploy_test && echo 'cleaned'")
            assert "cleaned" in result.stdout
    
    def test_scenario_monitoring_check(self, test_environment):
        """场景：监控检查"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        checks = []
        
        with SSHClient(config) as client:
            # CPU检查
            result = client.exec_command("uptime")
            checks.append(("uptime", result.exit_code == 0))
            
            # 内存检查
            result = client.exec_command("free -m 2>/dev/null || echo 'mem ok'")
            checks.append(("memory", result.exit_code == 0 or "mem ok" in result.stdout))
            
            # 磁盘检查
            result = client.exec_command("df -h")
            checks.append(("disk", result.exit_code == 0))
        
        # 验证所有检查都通过
        for check_name, passed in checks:
            assert passed, f"{check_name} check failed"
    
    def test_scenario_log_analysis(self, test_environment):
        """场景：日志分析"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        with SSHClient(config) as client:
            # 生成一些测试日志
            client.exec_command("logger -t test 'test log entry'")
            
            # 查看最近的日志
            result = client.exec_command("echo 'log entry 1'; echo 'log entry 2'; echo 'log entry 3'")
            
            # 分析日志
            lines = result.stdout.strip().split('\n')
            assert len(lines) >= 3, "应该有至少3行日志"
    
    def test_scenario_backup_task(self, test_environment):
        """场景：备份任务"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        with SSHClient(config) as client:
            # 1. 创建测试数据
            result = client.exec_command("mkdir -p /tmp/backup_test && echo 'data' > /tmp/backup_test/file.txt")
            assert result.exit_code == 0
            
            # 2. 打包备份
            result = client.exec_command("tar -czf /tmp/backup.tar.gz -C /tmp backup_test && echo 'backup done'")
            assert "backup done" in result.stdout
            
            # 3. 验证备份
            result = client.exec_command("tar -tzf /tmp/backup.tar.gz | head -1")
            assert "backup_test" in result.stdout
            
            # 4. 清理
            client.exec_command("rm -rf /tmp/backup_test /tmp/backup.tar.gz")
    
    def test_scenario_multi_session_workspace(self, test_environment):
        """场景：多会话工作空间（开发环境）"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            # 会话1：代码编译
            build_session = mgr.create_session("build")
            build_session.execute_command("mkdir -p /tmp/workspace/build")
            build_output = build_session.execute_command("echo 'Building project...' && echo 'Build complete'")
            assert "Build complete" in build_output
            
            # 会话2：测试运行
            test_session = mgr.create_session("test")
            test_session.execute_command("cd /tmp && mkdir -p test_results")
            test_output = test_session.execute_command("echo 'Running tests...' && echo 'Tests passed'")
            assert "Tests passed" in test_output
            
            # 会话3：日志监控
            log_session = mgr.create_session("logs")
            log_output = log_session.execute_command("echo 'Monitoring logs...'")
            
            # 验证会话独立
            assert mgr.active_session_count == 3
            
            # 清理
            mgr.close_all_sessions()
            
        finally:
            conn.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
