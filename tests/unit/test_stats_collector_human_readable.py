"""
测试连接池统计收集器的人类可读格式功能
"""

import time
import pytest
from unittest.mock import Mock, patch

from src.pooling.stats_collector import PoolStatsCollector, PoolMetrics


class TestPoolStatsCollectorHumanReadable:
    """测试统计收集器的人类可读格式"""

    def test_get_stats_default_human_readable(self):
        """测试默认返回人类可读格式"""
        stats = PoolStatsCollector()
        stats.record_connection_created()
        stats.record_acquire_time(0.5)
        stats.record_wait_time(0.2)

        result = stats.get_stats(current_pool_size=2, current_in_use=1, max_size=5)

        # 验证时间字段是字符串格式
        assert isinstance(result["avg_acquire_time"], str)
        assert isinstance(result["avg_wait_time"], str)
        assert isinstance(result["uptime"], str)
        assert isinstance(result["created_at"], str)
        assert "ms" in result["avg_acquire_time"] or "s" in result["avg_acquire_time"]

    def test_get_stats_raw_format(self):
        """测试返回原始数值格式"""
        stats = PoolStatsCollector()
        stats.record_connection_created()
        stats.record_acquire_time(0.5)

        result = stats.get_stats(
            current_pool_size=2, current_in_use=1, max_size=5, human_readable=False
        )

        # 验证时间字段是数值格式
        assert isinstance(result["avg_acquire_time"], float)
        assert isinstance(result["created_at"], float)
        assert result["avg_acquire_time"] == 0.5

    def test_format_duration_milliseconds(self):
        """测试毫秒格式"""
        stats = PoolStatsCollector()

        result = stats._format_duration(0.05)
        assert "ms" in result

        result = stats._format_duration(0.5)
        assert "ms" in result or "s" in result

    def test_format_duration_seconds(self):
        """测试秒格式"""
        stats = PoolStatsCollector()

        result = stats._format_duration(5.5)
        assert "s" in result
        assert "ms" not in result

    def test_format_duration_minutes(self):
        """测试分钟格式"""
        stats = PoolStatsCollector()

        result = stats._format_duration(65)
        assert "m" in result

    def test_format_duration_hours(self):
        """测试小时格式"""
        stats = PoolStatsCollector()

        result = stats._format_duration(3665)  # 1小时1分5秒
        assert "h" in result

    def test_format_duration_days(self):
        """测试天格式"""
        stats = PoolStatsCollector()

        result = stats._format_duration(90000)  # 超过1天
        assert "d" in result

    def test_format_timestamp(self):
        """测试时间戳格式化"""
        stats = PoolStatsCollector()

        timestamp = time.time()
        result = stats._format_timestamp(timestamp)

        # 格式应该是 MM-DD HH:MM
        assert len(result.split()) == 2
        assert "-" in result.split()[0]
        assert ":" in result.split()[1]

    def test_format_uptime(self):
        """测试运行时间格式化"""
        stats = PoolStatsCollector()

        # 测试不同时间范围
        assert stats._format_uptime(30) == "30s"
        assert stats._format_uptime(90) == "1m30s"
        assert "h" in stats._format_uptime(3700)
        assert "d" in stats._format_uptime(90000)

    def test_time_fields_in_stats(self):
        """测试统计信息中的时间字段"""
        stats = PoolStatsCollector()
        stats.record_connection_created()
        stats.record_acquire_time(0.5)
        stats.record_wait_time(0.2)
        stats.record_connection_lifetime(10.5)

        result = stats.get_stats(current_pool_size=1, current_in_use=0, max_size=5)

        # 验证所有时间字段都存在且格式正确
        time_fields = [
            "avg_lifetime",
            "avg_wait_time",
            "avg_wait_time_recent",
            "avg_acquire_time",
            "max_acquire_time",
            "total_wait_time",
            "uptime",
            "created_at",
            "last_activity",
        ]

        for field in time_fields:
            assert field in result, f"字段 {field} 不存在"
            assert isinstance(result[field], str), f"字段 {field} 不是字符串格式"

    def test_stats_with_no_data(self):
        """测试无数据时的统计信息"""
        stats = PoolStatsCollector()

        result = stats.get_stats(current_pool_size=0, current_in_use=0, max_size=5)

        # 验证无数据时返回合理的默认值
        assert result["avg_acquire_time"] in ["0s", "0ms", "0.0s"]
        assert result["avg_wait_time"] in ["0s", "0ms", "0.0s"]

    def test_disabled_stats(self):
        """测试禁用统计功能"""
        stats = PoolStatsCollector(enabled=False)

        result = stats.get_stats()
        assert result == {"enabled": False}


class TestPoolStatsCollectorReset:
    """测试统计收集器的重置功能"""

    def test_reset_clears_all_stats(self):
        """测试重置清除所有统计"""
        stats = PoolStatsCollector()

        # 添加一些统计数据
        stats.record_connection_created()
        stats.record_connection_reused()
        stats.record_acquire_time(0.5)
        stats.record_wait_time(0.2)

        # 重置
        stats.reset()

        # 验证所有计数器归零
        metrics = stats.get_metrics()
        assert metrics.created == 0
        assert metrics.reused == 0
        assert metrics.waits == 0

        # 验证历史数据被清除
        assert len(stats.get_acquire_times()) == 0
        assert len(stats.get_wait_times()) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
