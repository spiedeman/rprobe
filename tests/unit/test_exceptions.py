"""
异常模块测试

提升 src/exceptions/__init__.py 的覆盖率
"""

import pytest

from rprobe.exceptions import (
    SSHError,
    ConnectionError,
    AuthenticationError,
    CommandTimeoutError,
    CommandExecutionError,
    SessionError,
    PromptDetectionError,
    ConfigurationError,
    PoolError,
    PoolExhaustedError,
    PoolTimeoutError,
    ReceiverError,
    ValidationError,
)


class TestSSHError:
    """测试基础SSH异常"""

    def test_basic_error(self):
        """测试基础错误"""
        error = SSHError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.error_code == "SSH_ERROR"
        assert str(error) == "[SSH_ERROR] Something went wrong"

    def test_error_with_custom_code(self):
        """测试自定义错误码"""
        error = SSHError("Custom error", error_code="CUSTOM_ERROR")
        assert error.error_code == "CUSTOM_ERROR"
        assert "[CUSTOM_ERROR]" in str(error)


class TestConnectionError:
    """测试连接错误"""

    def test_basic_connection_error(self):
        """测试基础连接错误"""
        error = ConnectionError("example.com", 22)
        assert error.host == "example.com"
        assert error.port == 22
        assert error.reason == ""
        assert "example.com:22" in str(error)

    def test_connection_error_with_reason(self):
        """测试带原因的连接错误"""
        error = ConnectionError("example.com", 22, "Connection refused")
        assert error.reason == "Connection refused"
        assert "Connection refused" in str(error)


class TestAuthenticationError:
    """测试认证错误"""

    def test_basic_auth_error(self):
        """测试基础认证错误"""
        error = AuthenticationError("example.com", "user")
        assert error.host == "example.com"
        assert error.username == "user"
        assert error.method == ""
        assert "user@example.com" in str(error)

    def test_auth_error_with_method(self):
        """测试带认证方式的错误"""
        error = AuthenticationError("example.com", "user", "password")
        assert error.method == "password"
        assert "using password" in str(error)


class TestCommandTimeoutError:
    """测试命令超时错误"""

    def test_timeout_without_host(self):
        """测试不带主机的超时"""
        error = CommandTimeoutError("ls -la", 30.0)
        assert error.command == "ls -la"
        assert error.timeout == 30.0
        assert error.host == ""
        assert "ls -la" in str(error)
        assert "30.0s" in str(error)

    def test_timeout_with_host(self):
        """测试带主机的超时"""
        error = CommandTimeoutError("ls -la", 30.0, "example.com")
        assert error.host == "example.com"
        assert "example.com" in str(error)


class TestCommandExecutionError:
    """测试命令执行错误"""

    def test_basic_execution_error(self):
        """测试基础执行错误"""
        error = CommandExecutionError("ls -la", 1)
        assert error.command == "ls -la"
        assert error.exit_code == 1
        assert error.stderr == ""
        assert error.host == ""

    def test_execution_error_with_stderr(self):
        """测试带错误输出的执行错误"""
        error = CommandExecutionError("ls -la", 1, stderr="No such file")
        assert error.stderr == "No such file"
        assert "No such file" in str(error)

    def test_execution_error_with_long_stderr(self):
        """测试长错误输出被截断"""
        long_stderr = "x" * 300
        error = CommandExecutionError("cmd", 1, stderr=long_stderr)
        assert len(str(error)) < 400  # 确保被截断

    def test_execution_error_with_host(self):
        """测试带主机的执行错误"""
        error = CommandExecutionError("cmd", 1, host="server.com")
        assert error.host == "server.com"
        assert "server.com" in str(error)


class TestSessionError:
    """测试会话错误"""

    def test_basic_session_error(self):
        """测试基础会话错误"""
        error = SessionError("Session closed unexpectedly")
        assert error.session_id == ""
        assert "Session closed unexpectedly" in str(error)

    def test_session_error_with_id(self):
        """测试带会话ID的错误"""
        error = SessionError("Session error", session_id="sess_123")
        assert error.session_id == "sess_123"


class TestPromptDetectionError:
    """测试提示符检测错误"""

    def test_basic_detection_error(self):
        """测试基础检测错误"""
        error = PromptDetectionError()
        assert error.output == ""
        assert error.expected_patterns == []
        assert "Failed to detect prompt" in str(error)

    def test_detection_error_with_output(self):
        """测试带输出的检测错误"""
        error = PromptDetectionError(output="some output text")
        assert error.output == "some output text"
        assert "some output" in str(error)

    def test_detection_error_with_patterns(self):
        """测试带期望模式的检测错误"""
        patterns = ["$", "#", ">"]
        error = PromptDetectionError(expected_patterns=patterns)
        assert error.expected_patterns == patterns

    def test_detection_error_with_long_output(self):
        """测试长输出被截断"""
        long_output = "x" * 200
        error = PromptDetectionError(output=long_output)
        # 输出应该被截断到100字符
        assert "..." in str(error) or len(str(error)) < 200


class TestConfigurationError:
    """测试配置错误"""

    def test_basic_config_error(self):
        """测试基础配置错误"""
        error = ConfigurationError("Invalid configuration")
        assert error.config_key == ""
        assert "Invalid configuration" in str(error)

    def test_config_error_with_key(self):
        """测试带配置键的错误"""
        error = ConfigurationError("Invalid value", config_key="timeout")
        assert error.config_key == "timeout"


class TestPoolError:
    """测试连接池错误"""

    def test_basic_pool_error(self):
        """测试基础连接池错误"""
        error = PoolError("Pool error")
        assert error.pool_size == 0
        assert error.max_size == 0

    def test_pool_error_with_sizes(self):
        """测试带大小信息的错误"""
        error = PoolError("Pool full", pool_size=10, max_size=10)
        assert error.pool_size == 10
        assert error.max_size == 10


class TestPoolExhaustedError:
    """测试连接池耗尽错误"""

    def test_pool_exhausted(self):
        """测试连接池耗尽"""
        error = PoolExhaustedError(max_size=10)
        assert error.max_size == 10
        assert "exhausted" in str(error).lower()
        assert "max_size=10" in str(error)


class TestPoolTimeoutError:
    """测试连接池超时错误"""

    def test_pool_timeout(self):
        """测试连接池获取超时"""
        error = PoolTimeoutError(timeout=30.0, max_size=10)
        assert error.timeout == 30.0
        assert error.max_size == 10
        assert "Timeout" in str(error)
        assert "30.0s" in str(error)
        assert "max_size=10" in str(error)


class TestReceiverError:
    """测试接收器错误"""

    def test_basic_receiver_error(self):
        """测试基础接收器错误"""
        error = ReceiverError("Receive failed")
        assert error.channel_id == ""
        assert "Receive failed" in str(error)

    def test_receiver_error_with_channel(self):
        """测试带通道ID的接收器错误"""
        error = ReceiverError("Receive failed", channel_id="ch_123")
        assert error.channel_id == "ch_123"


class TestValidationError:
    """测试验证错误"""

    def test_basic_validation_error(self):
        """测试基础验证错误"""
        error = ValidationError("Invalid data")
        assert error.field == ""
        assert "Invalid data" in str(error)

    def test_validation_error_with_field(self):
        """测试带字段的验证错误"""
        error = ValidationError("Required field", field="username")
        assert error.field == "username"


class TestExceptionHierarchy:
    """测试异常继承关系"""

    def test_all_exceptions_inherit_ssh_error(self):
        """测试所有异常都继承SSHError"""
        exceptions = [
            ConnectionError("host"),
            AuthenticationError("host", "user"),
            CommandTimeoutError("cmd", 10),
            CommandExecutionError("cmd", 1),
            SessionError("error"),
            PromptDetectionError(),
            ConfigurationError("error"),
            PoolError("error"),
            PoolExhaustedError(10),
            PoolTimeoutError(10, 5),
            ReceiverError("error"),
            ValidationError("error"),
        ]

        for exc in exceptions:
            assert isinstance(exc, SSHError)

    def test_pool_errors_inherit_pool_error(self):
        """测试连接池错误继承关系"""
        assert isinstance(PoolExhaustedError(10), PoolError)
        assert isinstance(PoolTimeoutError(10, 5), PoolError)
        assert isinstance(PoolExhaustedError(10), SSHError)
        assert isinstance(PoolTimeoutError(10, 5), SSHError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
