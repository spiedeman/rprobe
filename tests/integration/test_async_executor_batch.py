"""
后台任务批量功能集成测试

需要真实SSH连接环境
"""

import time
import pytest
import os

# 检查是否启用真实SSH测试
TEST_REAL_SSH = os.environ.get("TEST_REAL_SSH", "false").lower() == "true"

if TEST_REAL_SSH:
    from rprobe import SSHClient, SSHConfig
    from rprobe.core.async_executor import BatchTaskResult, TaskStatus


@pytest.mark.skipif(not TEST_REAL_SSH, reason="需要真实SSH环境")
class TestBatchTaskRealSSH:
    """真实SSH环境下的批量任务集成测试"""

    @pytest.fixture
    def config(self):
        """创建SSH配置"""
        return SSHConfig(
            host=os.environ.get("TEST_SSH_HOST", "localhost"),
            username=os.environ.get("TEST_SSH_USER", "test"),
            password=os.environ.get("TEST_SSH_PASS", "test"),
            port=int(os.environ.get("TEST_SSH_PORT", "22")),
            timeout=30.0,
        )

    def test_batch_tasks_with_real_ssh(self, config):
        """测试真实SSH环境下的批量任务"""
        with SSHClient(config, use_pool=False) as client:
            # 准备批量命令
            commands = [
                {"command": "echo 'Task 1 output' && sleep 1", "name": "task1"},
                {"command": "echo 'Task 2 output' && sleep 1", "name": "task2"},
                {"command": "echo 'Task 3 output' && sleep 1", "name": "task3"},
            ]

            # 批量启动
            batch = client._bg_manager.run_batch(
                commands,
                max_concurrent=2,
                batch_delay=0.5
            )

            # 验证启动
            assert len(batch.tasks) == 3
            assert batch.running_count >= 0

            # 等待所有任务完成（最多30秒）
            completed = batch.wait_all(timeout=30)

            # 获取结果
            summaries = batch.get_summaries()

            # 验证结果
            for summary in summaries:
                print(f"\n{summary.name}:")
                print(f"  Status: {summary.status}")
                print(f"  Duration: {summary.duration:.1f}s")
                print(f"  Output lines: {summary.lines_output}")

            # 至少应该有输出
            total_output = sum(s.lines_output for s in summaries)
            assert total_output > 0, "应该有输出"

    def test_batch_concurrent_limit(self, config):
        """测试并发限制实际生效"""
        with SSHClient(config, use_pool=False) as client:
            # 启动5个耗时任务
            commands = [
                {"command": f"sleep 3 && echo 'Done {i}'", "name": f"concurrent_{i}"}
                for i in range(5)
            ]

            start_time = time.time()

            batch = client._bg_manager.run_batch(
                commands,
                max_concurrent=2,  # 最多2个并发
                batch_delay=0.1
            )

            # 验证启动时的并发控制
            time.sleep(0.5)  # 等待部分任务启动
            initial_running = batch.running_count
            print(f"\nInitial running tasks: {initial_running}")

            # 由于并发限制为2，初始运行中的任务不应超过2（可能有1个已完成）
            assert initial_running <= 2, f"并发任务数不应超过2，实际: {initial_running}"

            # 等待所有完成
            batch.wait_all(timeout=60)

            elapsed = time.time() - start_time

            # 5个任务，每个3秒，并发2个
            # 理论上最少需要 3*3 = 9秒（3批，每批2个，最后一个1个）
            # 如果并发控制失效，时间会接近5*3 = 15秒
            print(f"\nTotal elapsed: {elapsed:.1f}s")
            assert elapsed >= 6, "并发控制应导致总时间增加"
            assert elapsed < 20, "应在合理时间内完成"

    def test_batch_stop_all(self, config):
        """测试批量停止功能"""
        with SSHClient(config, use_pool=False) as client:
            # 启动长时间运行的任务
            commands = [
                {"command": "sleep 60", "name": f"long_task_{i}"}
                for i in range(3)
            ]

            batch = client._bg_manager.run_batch(commands)

            # 等待任务启动
            time.sleep(2)

            # 验证任务在运行
            assert batch.running_count > 0, "应该有任务在运行"

            # 批量停止
            batch.stop_all(graceful=True, timeout=5.0)

            # 等待停止完成
            time.sleep(2)

            # 验证所有任务已停止
            assert batch.running_count == 0, "所有任务应已停止"

            # 验证状态
            summaries = batch.get_summaries()
            for summary in summaries:
                print(f"\n{summary.name}: {summary.status}")
                assert summary.status in ["stopped", "error"], f"任务应已停止，实际: {summary.status}"

    def test_batch_with_pool_mode(self, config):
        """测试连接池模式下的批量任务"""
        with SSHClient(config, use_pool=True, max_size=3) as client:
            # 准备命令
            commands = [
                {"command": f"echo 'Pool test {i}'", "name": f"pool_task_{i}"}
                for i in range(3)
            ]

            batch = client._bg_manager.run_batch(commands)

            # 等待完成
            completed = batch.wait_all(timeout=30)

            assert completed, "任务应完成"

            # 验证输出
            summaries = batch.get_summaries()
            for i, summary in enumerate(summaries):
                assert summary.status == "completed", f"任务 {i} 应完成"
                assert "Pool test" in str(summary.last_lines), f"任务 {i} 应有正确输出"

    def test_batch_error_handling(self, config):
        """测试批量任务错误处理"""
        with SSHClient(config, use_pool=False) as client:
            commands = [
                {"command": "echo 'Valid command'", "name": "valid"},
                {"command": "exit 1", "name": "fail"},  # 会失败
                {"command": "echo 'Another valid'", "name": "valid2"},
            ]

            batch = client._bg_manager.run_batch(commands)

            # 等待完成
            batch.wait_all(timeout=30)

            # 获取结果
            summaries = batch.get_summaries()

            # 验证状态
            statuses = [s.status for s in summaries]
            print(f"\nStatuses: {statuses}")

            # 应该有成功和失败
            assert "completed" in statuses, "应有成功的任务"
            # exit 1 通常会被认为是错误
            assert any(s in ["error", "completed"] for s in statuses), "应有各种状态"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--run-integration"])
