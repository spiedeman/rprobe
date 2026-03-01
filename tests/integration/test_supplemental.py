"""
补充的集成测试 - 网络恢复、会话恢复、安全测试
"""

import time
import pytest
import logging

from rprobe import SSHClient, SSHConfig
from rprobe.pooling import ConnectionPool
from rprobe.core.connection import ConnectionManager, MultiSessionManager


@pytest.mark.integration
class TestNetworkRecovery:
    """测试网络闪断恢复能力"""

    def test_connection_recovery_after_brief_disconnect(self, test_environment):
        """测试短暂断开后连接恢复"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=5.0,
            command_timeout=10.0,
        )

        # 先建立连接
        conn = ConnectionManager(config)
        conn.connect()
        assert conn.is_connected

        # 模拟短暂断开（通过重置连接）
        conn.disconnect()
        assert not conn.is_connected

        # 重新连接
        conn.connect()
        assert conn.is_connected

        # 验证连接可用
        channel = conn.open_channel()
        assert channel is not None
        channel.close()

        conn.disconnect()

    def test_pool_recovery_after_connection_loss(self, test_environment):
        """测试连接池在连接丢失后恢复"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=5.0,
            command_timeout=10.0,
        )

        pool = ConnectionPool(config, max_size=2, min_size=1, health_check_interval=0)

        try:
            # 正常使用连接
            with pool.get_connection() as conn:
                assert conn.is_connected

            # 模拟连接丢失（关闭后重置）
            pool.close()
            pool.reset()

            # 验证连接池恢复
            assert not pool._closed
            assert pool.stats["pool_size"] >= 1

            # 验证可以正常使用
            with pool.get_connection() as conn:
                assert conn.is_connected
        finally:
            pool.close()


@pytest.mark.integration
class TestSessionRecovery:
    """测试会话异常恢复"""

    def test_session_recreate_after_channel_close(self, test_environment):
        """测试channel关闭后会话重建"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        conn = ConnectionManager(config)
        conn.connect()

        try:
            mgr = MultiSessionManager(conn, config)

            # 创建会话
            session1 = mgr.create_session("test_session")

            # 验证会话可用
            output1 = session1.execute_command("echo 'before'")
            assert "before" in output1

            # 关闭会话（模拟异常）
            mgr.close_session("test_session")

            # 重建会话（使用不同名称，因为原会话还在管理中）
            session2 = mgr.create_session("test_session_new")

            # 验证新会话可用
            output2 = session2.execute_command("echo 'after'")
            assert "after" in output2

            mgr.close_all_sessions()
        finally:
            conn.disconnect()

    def test_multiple_sessions_with_one_failure(self, test_environment):
        """测试多个会话中一个失败时不影响其他"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=10.0,
            command_timeout=30.0,
        )

        conn = ConnectionManager(config)
        conn.connect()

        try:
            mgr = MultiSessionManager(conn, config)

            # 创建两个会话
            session1 = mgr.create_session("session1")
            session2 = mgr.create_session("session2")

            # 使用两个会话
            out1 = session1.execute_command("echo 's1'")
            out2 = session2.execute_command("echo 's2'")

            assert "s1" in out1
            assert "s2" in out2

            # 关闭其中一个
            mgr.close_session("session1")

            # 验证另一个仍然可用
            out2_again = session2.execute_command("echo 's2_again'")
            assert "s2_again" in out2_again

            mgr.close_all_sessions()
        finally:
            conn.disconnect()


@pytest.mark.integration
class TestSecurityAndLogging:
    """测试安全和日志相关"""

    def test_password_not_in_logs(self, test_environment, caplog):
        """测试密码不会出现在日志中"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        # 设置日志级别为DEBUG以捕获所有日志
        with caplog.at_level(logging.DEBUG):
            config = SSHConfig(
                host=test_environment["test_host"],
                username=test_environment["test_user"],
                password=test_environment["test_pass"],  # 使用真实密码进行测试
                timeout=5.0,
                command_timeout=10.0,
            )

            # 建立连接
            conn = ConnectionManager(config)
            try:
                conn.connect()
                # 执行简单命令
                channel = conn.open_channel()
                channel.close()
            finally:
                conn.disconnect()

        # 检查日志中不应出现密码
        log_text = caplog.text
        assert "secret_password_123" not in log_text, "密码不应出现在日志中"
        assert test_environment["test_pass"] not in log_text, "真实密码不应出现在日志中"

    def test_sensitive_info_masked_in_output(self, test_environment):
        """测试敏感信息在输出中被掩码"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=5.0,
            command_timeout=10.0,
        )

        with SSHClient(config) as client:
            # 执行命令查看环境变量
            result = client.exec_command("env | grep -i pass || echo 'no password in env'")

            # 环境变量中不应包含密码
            assert test_environment["test_pass"] not in result.stdout


@pytest.mark.integration
class TestDataTransmission:
    """测试数据传输"""

    def test_large_data_transfer(self, test_environment):
        """测试大数据传输能力（使用流式API，累计500KB）"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=30.0,
            command_timeout=60.0,
            max_output_size=10 * 1024 * 1024,  # 10MB
        )

        with SSHClient(config) as client:
            # 使用流式API测试大数据传输
            # 这种模式下数据通过回调函数实时处理，不受缓冲区限制
            total_size = 0
            received_chunks = []

            def handle_chunk(stdout, stderr):
                nonlocal total_size
                if stdout:
                    total_size += len(stdout)
                    received_chunks.append(stdout)

            # 生成 500KB 数据
            target_size = 500000  # 500KB
            result = client.exec_command_stream(
                f"yes A | head -c {target_size}", handle_chunk, timeout=60.0
            )

            # 验证结果
            assert result.exit_code == 0, f"命令执行失败: exit_code={result.exit_code}"
            assert (
                total_size == target_size
            ), f"传输大小不正确: {total_size} bytes (期望 {target_size})"

            # 验证数据完整性（检查所有数据块是否都是 'A' 字符）
            all_data = b"".join(received_chunks)
            assert len(all_data) == target_size, f"数据块总大小不正确"
            assert all(c == ord("A") or c == ord("\n") for c in all_data[:1000]), "数据内容不正确"

    def test_large_data_transfer_streaming_performance(self, test_environment):
        """测试流式API的性能优势（1MB数据传输）"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=30.0,
            command_timeout=120.0,
        )

        import time

        with SSHClient(config) as client:
            target_size = 1024 * 1024  # 1MB
            chunk_sizes = []
            total_received = 0

            def handle_chunk(stdout, stderr):
                nonlocal total_received
                if stdout:
                    chunk_sizes.append(len(stdout))
                    total_received += len(stdout)

            start_time = time.time()
            result = client.exec_command_stream(
                f"yes B | head -c {target_size}", handle_chunk, timeout=120.0
            )
            elapsed = time.time() - start_time

            # 验证结果
            assert result.exit_code == 0
            assert total_received == target_size, f"传输不完整: {total_received}/{target_size}"

            # 验证流式特性（应该有多个数据块）
            assert len(chunk_sizes) > 1, f"应该分多次接收，实际只收到 {len(chunk_sizes)} 个数据块"

            print(f"\n流式传输性能测试:")
            print(f"  总大小: {target_size / 1024:.0f}KB")
            print(f"  数据块数: {len(chunk_sizes)}")
            print(f"  平均块大小: {sum(chunk_sizes) / len(chunk_sizes):.0f} bytes")
            print(f"  最大块: {max(chunk_sizes)} bytes")
            print(f"  耗时: {elapsed:.2f}s")
            print(f"  速度: {target_size / 1024 / elapsed:.1f} KB/s")

    def test_special_characters_in_command(self, test_environment):
        """测试特殊字符命令处理"""
        if not test_environment["has_real_ssh"]:
            pytest.skip("未设置真实 SSH 测试环境变量")

        config = SSHConfig(
            host=test_environment["test_host"],
            username=test_environment["test_user"],
            password=test_environment["test_pass"],
            timeout=5.0,
            command_timeout=10.0,
        )

        with SSHClient(config) as client:
            # 测试包含特殊字符的命令
            test_cases = [
                ("echo 'Hello World'", "Hello World"),
                ("echo 'Test $VAR'", "Test $VAR"),  # 变量不应被展开
                ("echo 'Quote: \"'", '"'),  # 引号处理
            ]

            for cmd, expected in test_cases:
                result = client.exec_command(cmd)
                assert result.exit_code == 0
                assert expected in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
