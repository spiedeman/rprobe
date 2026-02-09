"""
CommandResult 单元测试
"""
import pytest

from src.core.models import CommandResult


class TestCommandResult:
    """测试 CommandResult 数据类"""

    def test_success_result(self):
        """测试成功的命令结果"""
        result = CommandResult(
            stdout="Hello World\n",
            stderr="",
            exit_code=0,
            execution_time=0.123,
            command="echo 'Hello World'"
        )
        
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "Hello World\n"
        assert result.stderr == ""
        assert result.execution_time == 0.123
        assert result.command == "echo 'Hello World'"

    def test_failure_result(self):
        """测试失败的命令结果"""
        result = CommandResult(
            stdout="",
            stderr="Error: file not found",
            exit_code=1,
            execution_time=0.045,
            command="cat nonexistent"
        )
        
        assert result.success is False
        assert result.exit_code == 1
        assert "Error" in result.stderr

    def test_string_representation(self):
        """测试字符串表示"""
        result = CommandResult(
            stdout="output",
            stderr="error",
            exit_code=0,
            execution_time=1.234,
            command="test_cmd"
        )
        
        str_repr = str(result)
        
        assert "test_cmd" in str_repr
        assert "成功" in str_repr
        assert "0" in str_repr  # exit_code
        assert "1.234" in str_repr  # execution_time

    def test_result_equality(self):
        """测试结果相等性"""
        result1 = CommandResult("out", "err", 0, 0.1, "cmd")
        result2 = CommandResult("out", "err", 0, 0.1, "cmd")
        result3 = CommandResult("out", "err", 1, 0.1, "cmd")
        
        assert result1 == result2
        assert result1 != result3

    def test_result_with_large_output(self):
        """测试大输出结果"""
        large_output = "A" * 10000
        result = CommandResult(
            stdout=large_output,
            stderr="",
            exit_code=0,
            execution_time=5.0,
            command="generate_large_output"
        )
        
        assert len(result.stdout) == 10000
        assert result.success is True


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_output(self):
        """测试空输出"""
        result = CommandResult(
            stdout="",
            stderr="",
            exit_code=0,
            execution_time=0.001,
            command="true"
        )
        
        assert result.stdout == ""
        assert result.success is True

    def test_multiline_output(self):
        """测试多行输出"""
        stdout = "line1\nline2\nline3\n"
        result = CommandResult(
            stdout=stdout,
            stderr="",
            exit_code=0,
            execution_time=0.1,
            command="echo_multiple"
        )
        
        lines = result.stdout.strip().split('\n')
        assert len(lines) == 3

    def test_unicode_output(self):
        """测试 Unicode 输出"""
        result = CommandResult(
            stdout="你好世界 🌍\n",
            stderr="错误信息",
            exit_code=0,
            execution_time=0.1,
            command="echo_unicode"
        )
        
        assert "你好世界" in result.stdout
        assert "🌍" in result.stdout
        assert "错误信息" in result.stderr

    def test_zero_execution_time(self):
        """测试零执行时间"""
        result = CommandResult(
            stdout="",
            stderr="",
            exit_code=0,
            execution_time=0.0,
            command="instant"
        )
        
        assert result.execution_time == 0.0
        assert "0.000" in str(result)
