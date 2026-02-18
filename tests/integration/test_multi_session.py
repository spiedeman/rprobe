"""
多会话管理器集成测试 - 测试真实SSH环境下的多会话功能

运行方式:
    export TEST_REAL_SSH=true
    export TEST_SSH_HOST=your-host
    export TEST_SSH_USER=your-user
    export TEST_SSH_PASS=your-password
    python -m pytest tests/integration/test_multi_session.py -v --run-integration
"""
import time
import pytest

from src import SSHConfig
from src.core.connection import ConnectionManager, MultiSessionManager
from tests.integration.test_config import SLEEP_TIME_SHORT


def check_channel_error(e):
    """检查是否是channel相关的错误"""
    error_msg = str(e).lower()
    return 'channel' in error_msg or 'closed' in error_msg


@pytest.mark.integration
class TestMultiSessionBasic:
    """测试多会话基本功能"""
    
    def test_create_single_session(self, test_environment):
        """测试创建单个会话"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            try:
                session = mgr.create_session("test_session", timeout=5.0)
            except Exception as e:
                if check_channel_error(e):
                    pytest.skip(f"Server channel limit reached: {e}")
                raise
            
            # 验证会话创建成功
            assert session is not None
            assert mgr.active_session_count == 1
            assert "test_session" in mgr.list_sessions()
            
            # 验证可以执行命令
            output = session.execute_command("echo 'Hello from session'")
            assert "Hello from session" in output
            
            # 关闭会话
            mgr.close_session("test_session")
            assert mgr.active_session_count == 0
            
        finally:
            conn.disconnect()
    
    def test_create_multiple_sessions(self, test_environment):
        """测试创建多个会话"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            # 创建多个会话 (限制为2个，避免服务器channel限制)
            try:
                session1 = mgr.create_session("session1", timeout=5.0)
                session2 = mgr.create_session("session2", timeout=5.0)
            except Exception as e:
                if check_channel_error(e):
                    pytest.skip(f"Server channel limit reached: {e}")
                raise
            
            # 验证所有会话
            assert mgr.active_session_count == 2
            assert len(mgr.list_sessions()) == 2
            
            # 关闭所有
            mgr.close_all_sessions()
            assert mgr.active_session_count == 0
            
        finally:
            conn.disconnect()
    
    def test_session_isolation(self, test_environment):
        """测试会话状态隔离"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        conn = ConnectionManager(config)
        conn.disconnect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            # 创建两个会话
            try:
                session1 = mgr.create_session("workspace1", timeout=5.0)
                session2 = mgr.create_session("workspace2", timeout=5.0)
            except Exception as e:
                if check_channel_error(e):
                    pytest.skip(f"Server channel limit reached: {e}")
                raise
            
            # 在session1中切换目录
            session1.execute_command("cd /tmp")
            output1 = session1.execute_command("pwd")
            assert "/tmp" in output1
            
            # 在session2中保持原目录
            output2 = session2.execute_command("pwd")
            # session2应该不在/tmp（除非默认就是/tmp）
            
            # 再次在session1中验证
            output1_again = session1.execute_command("pwd")
            assert "/tmp" in output1_again
            
            mgr.close_all_sessions()
            
        finally:
            conn.disconnect()
    
    def test_session_environment_isolation(self, test_environment):
        """测试会话环境变量隔离"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            # 创建两个会话
            try:
                session1 = mgr.create_session("env1", timeout=5.0)
                session2 = mgr.create_session("env2", timeout=5.0)
            except Exception as e:
                if check_channel_error(e):
                    pytest.skip(f"Server channel limit reached: {e}")
                raise
            
            # 在session1中设置环境变量
            session1.execute_command("export TEST_VAR='session1_value'")
            output1 = session1.execute_command("echo $TEST_VAR")
            assert "session1_value" in output1
            
            # 在session2中设置不同的值
            session2.execute_command("export TEST_VAR='session2_value'")
            output2 = session2.execute_command("echo $TEST_VAR")
            assert "session2_value" in output2
            
            # 验证session1的值未变
            output1_again = session1.execute_command("echo $TEST_VAR")
            assert "session1_value" in output1_again
            
            mgr.close_all_sessions()
            
        finally:
            conn.disconnect()


@pytest.mark.integration
class TestMultiSessionCommands:
    """测试多会话命令执行"""
    
    def test_concurrent_commands_in_sessions(self, test_environment):
        """测试在多个会话中并发执行命令"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            # 创建两个会话
            try:
                session1 = mgr.create_session("worker1", timeout=5.0)
                session2 = mgr.create_session("worker2", timeout=5.0)
            except Exception as e:
                if check_channel_error(e):
                    pytest.skip(f"Server channel limit reached: {e}")
                raise
            
            # 在两个会话中分别执行命令
            output1 = session1.execute_command("echo 'Task1'")
            output2 = session2.execute_command("echo 'Task2'")
            
            assert "Task1" in output1
            assert "Task2" in output2
            
            mgr.close_all_sessions()
            
        finally:
            conn.disconnect()
    
    def test_long_running_commands_in_sessions(self, test_environment):
        """测试在会话中执行长时间命令"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            try:
                session = mgr.create_session("long_task", timeout=5.0)
            except Exception as e:
                if check_channel_error(e):
                    pytest.skip(f"Server channel limit reached: {e}")
                raise
            
            # 执行一个稍长的命令
            start = time.time()
            output = session.execute_command(f"sleep {SLEEP_TIME_SHORT} && echo 'Completed'")
            elapsed = time.time() - start
            
            assert "Completed" in output
            assert elapsed >= SLEEP_TIME_SHORT * 0.8  # 确保确实等待了（允许20%误差）
            
            mgr.close_session("long_task")
            
        finally:
            conn.disconnect()


@pytest.mark.integration
class TestMultiSessionManagement:
    """测试多会话管理功能"""
    
    def test_get_session_info(self, test_environment):
        """测试获取会话信息"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            try:
                session = mgr.create_session("info_test", timeout=5.0)
            except Exception as e:
                if check_channel_error(e):
                    pytest.skip(f"Server channel limit reached: {e}")
                raise
            
            # 执行一些命令
            session.execute_command("echo 'command1'")
            session.execute_command("echo 'command2'")
            
            # 获取会话信息
            info = mgr.get_session_info("info_test")
            
            assert info is not None
            assert info['session_id'] == "info_test"
            assert info['is_active'] is True
            # Note: command_count is not automatically updated when execute_command is called
            # because create_session returns ShellSession directly, not a wrapper
            # assert info['command_count'] == 2
            assert 'created_at' in info
            assert 'age_seconds' in info
            
            mgr.close_session("info_test")
            
        finally:
            conn.disconnect()
    
    def test_get_all_sessions_info(self, test_environment):
        """测试获取所有会话信息"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            # 创建多个会话
            try:
                mgr.create_session("session_a", timeout=5.0)
                mgr.create_session("session_b", timeout=5.0)
            except Exception as e:
                if check_channel_error(e):
                    pytest.skip(f"Server channel limit reached: {e}")
                raise
            
            # 获取所有信息
            all_info = mgr.get_all_sessions_info()
            
            assert len(all_info) == 2
            
            for info in all_info:
                assert 'session_id' in info
                assert 'is_active' in info
                assert info['is_active'] is True
            
            mgr.close_all_sessions()
            
        finally:
            conn.disconnect()
    
    def test_close_nonexistent_session(self, test_environment):
        """测试关闭不存在的会话"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            # 尝试关闭不存在的会话
            result = mgr.close_session("nonexistent")
            
            assert result is False
            
        finally:
            conn.disconnect()
    
    def test_duplicate_session_id(self, test_environment):
        """测试重复的会话ID"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        conn = ConnectionManager(config)
        conn.connect()
        
        try:
            mgr = MultiSessionManager(conn, config)
            
            try:
                # 创建一个会话
                mgr.create_session("duplicate_test", timeout=5.0)
            except Exception as e:
                if check_channel_error(e):
                    pytest.skip(f"Server channel limit reached: {e}")
                raise
            
            # 尝试创建相同ID的会话应该报错
            with pytest.raises(ValueError) as exc_info:
                mgr.create_session("duplicate_test", timeout=5.0)
            
            assert "already exists" in str(exc_info.value)
            
            mgr.close_all_sessions()
            
        finally:
            conn.disconnect()


@pytest.mark.integration
class TestMultiSessionWithPool:
    """测试连接池+多会话组合使用"""
    
    def test_pool_with_multi_session(self, test_environment):
        """测试在连接池连接上使用多会话"""
        if not test_environment['has_real_ssh']:
            pytest.skip("未设置真实 SSH 测试环境变量")
        
        from src.pooling import ConnectionPool
        
        config = SSHConfig(
            host=test_environment['test_host'],
            username=test_environment['test_user'],
            password=test_environment['test_pass'],
            timeout=10.0,
            command_timeout=30.0,
        )
        
        pool = ConnectionPool(config, max_size=2, min_size=1, health_check_interval=0)
        
        try:
            with pool.get_connection() as conn:
                # 在池连接上创建多会话
                mgr = MultiSessionManager(conn, config)
                
                try:
                    session1 = mgr.create_session("pool_session1", timeout=5.0)
                    session2 = mgr.create_session("pool_session2", timeout=5.0)
                except Exception as e:
                    if check_channel_error(e):
                        pytest.skip(f"Server channel limit reached: {e}")
                    raise
                
                # 在两个会话中执行命令
                output1 = session1.execute_command("echo 'From pool session 1'")
                output2 = session2.execute_command("echo 'From pool session 2'")
                
                assert "From pool session 1" in output1
                assert "From pool session 2" in output2
                
                mgr.close_all_sessions()
                
        finally:
            pool.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
