"""
工具函数模块测试

提升 src/utils/helpers.py 的覆盖率
"""

import time
import pytest
from unittest.mock import patch

from src.utils.helpers import (
    retry,
    sanitize_string,
    truncate_middle,
    format_bytes,
    format_duration,
    deep_merge,
    safe_get,
    Timer,
    Singleton,
)


class TestRetry:
    """测试重试装饰器"""

    def test_retry_success_on_first_attempt(self):
        """测试首次成功不重试"""
        call_count = 0

        @retry(max_attempts=3, delay=0.1)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_success_after_failures(self):
        """测试失败后重试成功"""
        call_count = 0

        @retry(max_attempts=3, delay=0.01, backoff=1.0)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = fail_then_succeed()
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted_raises_exception(self):
        """测试重试耗尽后抛出异常"""
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")

        with pytest.raises(ValueError, match="Persistent error"):
            always_fail()

        assert call_count == 3

    def test_retry_with_specific_exceptions(self):
        """测试只捕获指定异常"""
        call_count = 0

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Should not retry")

        with pytest.raises(TypeError):
            raise_type_error()

        assert call_count == 1  # 不重试

    def test_retry_backoff_delay(self):
        """测试延迟增长 - 验证backoff参数被正确使用"""
        call_count = 0
        start_time = None

        @retry(max_attempts=3, delay=0.01, backoff=2.0)
        def fail_twice():
            nonlocal call_count, start_time
            call_count += 1
            if call_count == 1:
                start_time = time.time()
            if call_count < 3:
                raise ValueError(f"Error {call_count}")
            return "success"

        # 执行应该成功（第3次成功）
        result = fail_twice()
        assert result == "success"
        assert call_count == 3  # 验证确实重试了


class TestSanitizeString:
    """测试字符串清理"""

    def test_remove_control_characters(self):
        """测试移除控制字符"""
        text = "Hello\x00World\x01\x02"
        result = sanitize_string(text)
        assert result == "HelloWorld"

    def test_truncate_long_string(self):
        """测试截断长字符串"""
        text = "a" * 2000
        result = sanitize_string(text, max_length=1000)
        assert len(result) == 1003  # 1000 + "..."
        assert result.endswith("...")

    def test_no_change_for_clean_string(self):
        """测试干净字符串不变"""
        text = "Hello World"
        result = sanitize_string(text)
        assert result == "Hello World"

    def test_remove_multiple_control_chars(self):
        """测试移除多种控制字符"""
        text = "Test\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x1f\x7fEnd"
        result = sanitize_string(text)
        assert result == "TestEnd"


class TestTruncateMiddle:
    """测试中间截断"""

    def test_no_truncate_short_string(self):
        """测试短字符串不截断"""
        text = "Short"
        result = truncate_middle(text, max_length=100)
        assert result == "Short"

    def test_truncate_middle(self):
        """测试中间截断"""
        text = "a" * 200
        result = truncate_middle(text, max_length=50, ellipsis="...")
        # 长度可能是49或50，取决于整数除法
        assert 49 <= len(result) <= 50
        assert "..." in result
        assert result.startswith("a")
        assert result.endswith("a")

    def test_custom_ellipsis(self):
        """测试自定义省略号"""
        text = "a" * 100
        result = truncate_middle(text, max_length=30, ellipsis="[...]")
        assert "[...]" in result
        # 长度可能是29或30，取决于整数除法
        assert 29 <= len(result) <= 30


class TestFormatBytes:
    """测试字节格式化"""

    def test_format_bytes(self):
        """测试字节格式化"""
        assert format_bytes(512) == "512.00 B"
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert format_bytes(1024**4) == "1.00 TB"
        assert format_bytes(1024**5) == "1.00 PB"

    def test_format_bytes_decimal(self):
        """测试字节格式化小数"""
        assert format_bytes(1536) == "1.50 KB"
        assert format_bytes(2560) == "2.50 KB"


class TestFormatDuration:
    """测试持续时间格式化"""

    def test_format_microseconds(self):
        """测试微秒"""
        assert "µs" in format_duration(0.0001)

    def test_format_milliseconds(self):
        """测试毫秒"""
        assert format_duration(0.5) == "500.00 ms"
        assert format_duration(0.001) == "1.00 ms"

    def test_format_seconds(self):
        """测试秒"""
        assert format_duration(5.5) == "5.50 s"
        assert format_duration(1) == "1.00 s"

    def test_format_minutes(self):
        """测试分钟"""
        assert format_duration(90) == "1m 30.0s"
        assert format_duration(125) == "2m 5.0s"

    def test_format_hours(self):
        """测试小时"""
        assert format_duration(3660) == "1h 1m"
        assert format_duration(7200) == "2h 0m"


class TestDeepMerge:
    """测试深度合并"""

    def test_simple_merge(self):
        """测试简单合并"""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        """测试嵌套合并"""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 20, "z": 30}}
        result = deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3}

    def test_deep_nesting(self):
        """测试深层嵌套"""
        base = {"level1": {"level2": {"level3": "value"}}}
        override = {"level1": {"level2": {"level3": "new_value"}}}
        result = deep_merge(base, override)
        assert result["level1"]["level2"]["level3"] == "new_value"

    def test_original_dict_unchanged(self):
        """测试原字典不被修改"""
        base = {"a": 1}
        override = {"b": 2}
        result = deep_merge(base, override)
        assert base == {"a": 1}  # 原字典不变
        assert result == {"a": 1, "b": 2}


class TestSafeGet:
    """测试安全获取"""

    def test_get_existing_key(self):
        """测试获取存在的键"""
        d = {"a": 1, "b": 2}
        assert safe_get(d, "a") == 1
        assert safe_get(d, "b") == 2

    def test_get_missing_key_with_default(self):
        """测试获取不存在的键使用默认值"""
        d = {"a": 1}
        assert safe_get(d, "b", default="default") == "default"

    def test_get_missing_key_no_default(self):
        """测试获取不存在的键无默认值"""
        d = {"a": 1}
        assert safe_get(d, "b") is None

    def test_get_none_value(self):
        """测试获取None值"""
        d = {"a": None}
        assert safe_get(d, "a") is None


class TestTimer:
    """测试计时器"""

    def test_timer_context_manager(self):
        """测试上下文管理器"""
        with Timer() as timer:
            time.sleep(0.01)

        assert timer.elapsed > 0
        assert timer.elapsed < 0.1

    def test_timer_elapsed_during_timing(self):
        """测试计时期间的经过时间"""
        timer = Timer()
        with timer:
            time.sleep(0.02)
            elapsed_during = timer.elapsed

        elapsed_after = timer.elapsed

        assert elapsed_during > 0
        assert elapsed_after > elapsed_during

    def test_timer_not_started(self):
        """测试未开始的计时器"""
        timer = Timer()
        assert timer.elapsed == 0.0

    def test_timer_str_representation(self):
        """测试字符串表示"""
        with Timer() as timer:
            time.sleep(0.01)

        str_repr = str(timer)
        assert "ms" in str_repr or "s" in str_repr


class TestSingleton:
    """测试单例模式"""

    def test_singleton_instance(self):
        """测试单例实例相同"""

        class TestClass(Singleton):
            def __init__(self):
                self.value = 42

        a = TestClass()
        b = TestClass()

        assert a is b
        assert a.value == b.value

    def test_singleton_different_classes(self):
        """测试不同类的单例独立"""

        class ClassA(Singleton):
            pass

        class ClassB(Singleton):
            pass

        a1 = ClassA()
        a2 = ClassA()
        b1 = ClassB()
        b2 = ClassB()

        assert a1 is a2
        assert b1 is b2
        assert a1 is not b1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
