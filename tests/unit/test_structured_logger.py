"""
测试 StructuredLogger 的结构化字段功能
"""
import json
import logging
from io import StringIO
import pytest

from src.logging_config import (
    configure_logging,
    get_logger,
    StructuredLogger,
    JSONFormatter,
)


class TestStructuredLoggerFields:
    """测试结构化日志字段功能"""

    @pytest.fixture
    def setup_json_logger(self):
        """设置JSON格式的logger用于测试"""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(JSONFormatter())

        logger = logging.getLogger("test_structured")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        yield logger, log_stream

        # 清理
        logger.handlers.clear()

    def test_logger_accepts_keyword_arguments(self, setup_json_logger):
        """测试 logger.info 接受关键字参数"""
        logger, log_stream = setup_json_logger

        # 使用结构化字段
        logger.info(
            "command_executed",
            command="ls -la",
            duration_ms=150,
            exit_code=0,
            host="example.com"
        )

        # 解析JSON输出
        log_output = log_stream.getvalue()
        log_data = json.loads(log_output.strip())

        # 验证所有字段都被包含
        assert log_data["message"] == "command_executed"
        assert log_data["command"] == "ls -la"
        assert log_data["duration_ms"] == 150
        assert log_data["exit_code"] == 0
        assert log_data["host"] == "example.com"

    def test_logger_accepts_various_field_types(self, setup_json_logger):
        """测试 logger 接受不同类型的字段值"""
        logger, log_stream = setup_json_logger

        logger.info(
            "test_event",
            string_field="text",
            int_field=42,
            float_field=3.14,
            bool_field=True,
            list_field=["a", "b", "c"],
            dict_field={"key": "value"}
        )

        log_output = log_stream.getvalue()
        log_data = json.loads(log_output.strip())

        assert log_data["string_field"] == "text"
        assert log_data["int_field"] == 42
        assert log_data["float_field"] == 3.14
        assert log_data["bool_field"] is True
        assert log_data["list_field"] == ["a", "b", "c"]
        assert log_data["dict_field"] == {"key": "value"}

    def test_logger_with_context_binding(self, setup_json_logger):
        """测试上下文绑定功能"""
        logger, log_stream = setup_json_logger

        # 绑定上下文
        context_logger = logger.bind(request_id="abc123", user="admin")

        # 使用上下文logger
        context_logger.info(
            "operation_completed",
            operation="delete"
        )

        log_output = log_stream.getvalue()
        log_data = json.loads(log_output.strip())

        # 验证消息字段包含在context中
        assert log_data["message"] == "operation_completed"
        assert "context" in log_data
        assert log_data["context"]["request_id"] == "abc123"
        assert log_data["context"]["user"] == "admin"

    def test_logger_handles_empty_extra_fields(self, setup_json_logger):
        """测试无额外字段的情况"""
        logger, log_stream = setup_json_logger

        logger.info("simple_message")

        log_output = log_stream.getvalue()
        log_data = json.loads(log_output.strip())

        # 验证基本字段存在
        assert log_data["message"] == "simple_message"
        assert "timestamp" in log_data
        assert log_data["level"] == "INFO"

    def test_logger_all_levels_support_fields(self, setup_json_logger):
        """测试所有日志级别都支持结构化字段"""
        logger, log_stream = setup_json_logger
        logger.setLevel(logging.DEBUG)  # 设置DEBUG级别以捕获所有级别

        # 测试不同级别
        logger.debug("debug_msg", custom_field="debug")
        logger.info("info_msg", custom_field="info")
        logger.warning("warning_msg", custom_field="warning")
        logger.error("error_msg", custom_field="error")
        logger.critical("critical_msg", custom_field="critical")

        # 解析多行JSON
        log_lines = log_stream.getvalue().strip().split('\n')
        logs = [json.loads(line) for line in log_lines]

        # 验证每个级别都有自定义字段
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for i, level in enumerate(levels):
            assert logs[i]["level"] == level
            assert logs[i]["custom_field"] == level.lower()  # 自定义字段

    def test_structured_logger_registration(self):
        """测试 StructuredLogger 类已正确注册"""
        configure_logging(level="INFO", format="simple")
        logger = get_logger("test_registration")

        # 验证返回的是 StructuredLogger 类型
        assert isinstance(logger, StructuredLogger)

    def test_json_formatter_includes_custom_fields(self):
        """测试 JSONFormatter 正确包含自定义字段"""
        formatter = JSONFormatter()

        # 创建模拟的 LogRecord
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test_message",
            args=(),
            exc_info=None
        )
        # 添加自定义字段
        record.custom_field = "custom_value"
        record.command = "ls"

        output = formatter.format(record)
        data = json.loads(output)

        assert data["custom_field"] == "custom_value"
        assert data["command"] == "ls"
        assert data["message"] == "test_message"

    def test_configure_logging_with_handler(self):
        """测试 configure_logging 与自定义处理器的集成"""
        import logging
        from io import StringIO
        
        # 创建自定义处理器
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        
        # 配置日志
        configure_logging(level="INFO", format="simple")
        logger = get_logger("integration_test")
        
        # 添加自定义处理器
        logger.addHandler(handler)
        
        logger.info(
            "integration_test",
            custom_data="test_value"
        )
        
        # 验证消息被记录
        log_output = log_stream.getvalue()
        assert "integration_test" in log_output
        
        # 清理处理器
        logger.removeHandler(handler)


class TestStructuredLoggerEdgeCases:
    """测试边界情况"""

    @pytest.fixture
    def setup_json_logger(self):
        """设置JSON格式的logger用于测试"""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(JSONFormatter())

        logger = logging.getLogger("test_edge_cases")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        yield logger, log_stream

        logger.handlers.clear()

    def test_unicode_in_fields(self, setup_json_logger):
        """测试 Unicode 字符在字段中"""
        logger, log_stream = setup_json_logger

        logger.info(
            "unicode_test",
            chinese="中文",
            emoji="🎉",
            special="café"
        )

        log_output = log_stream.getvalue()
        log_data = json.loads(log_output.strip())

        assert log_data["chinese"] == "中文"
        assert log_data["emoji"] == "🎉"
        assert log_data["special"] == "café"

    def test_special_characters_in_field_names(self, setup_json_logger):
        """测试特殊字符在字段名中"""
        logger, log_stream = setup_json_logger

        logger.info(
            "special_chars",
            field_with_underscore="value1",
            field123="value2",
            FIELD_UPPER="value3"
        )

        log_output = log_stream.getvalue()
        log_data = json.loads(log_output.strip())

        assert log_data["field_with_underscore"] == "value1"
        assert log_data["field123"] == "value2"
        assert log_data["FIELD_UPPER"] == "value3"

    def test_none_values_in_fields(self, setup_json_logger):
        """测试 None 值在字段中"""
        logger, log_stream = setup_json_logger

        logger.info(
            "none_test",
            null_field=None,
            valid_field="value"
        )

        log_output = log_stream.getvalue()
        log_data = json.loads(log_output.strip())

        assert log_data["null_field"] is None
        assert log_data["valid_field"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
