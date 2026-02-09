"""
异常定义模块

提供精细化的异常类型，便于错误处理和问题定位。
"""


class SSHError(Exception):
    """SSH操作基础异常"""
    
    def __init__(self, message: str, error_code: str = "SSH_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)
    
    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class ConnectionError(SSHError):
    """连接错误"""
    
    def __init__(self, host: str, port: int = 22, reason: str = ""):
        self.host = host
        self.port = port
        self.reason = reason
        message = f"Failed to connect to {host}:{port}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, "CONNECTION_ERROR")


class AuthenticationError(SSHError):
    """认证错误"""
    
    def __init__(self, host: str, username: str, method: str = ""):
        self.host = host
        self.username = username
        self.method = method
        message = f"Authentication failed for {username}@{host}"
        if method:
            message += f" using {method}"
        super().__init__(message, "AUTHENTICATION_ERROR")


class CommandTimeoutError(SSHError):
    """命令超时错误"""
    
    def __init__(self, command: str, timeout: float, host: str = ""):
        self.command = command
        self.timeout = timeout
        self.host = host
        message = f"Command '{command}' timed out after {timeout}s"
        if host:
            message += f" on {host}"
        super().__init__(message, "COMMAND_TIMEOUT")


class CommandExecutionError(SSHError):
    """命令执行错误"""
    
    def __init__(self, command: str, exit_code: int, stderr: str = "", host: str = ""):
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        self.host = host
        message = f"Command '{command}' failed with exit code {exit_code}"
        if host:
            message += f" on {host}"
        if stderr:
            message += f": {stderr[:200]}"
        super().__init__(message, "COMMAND_EXECUTION_ERROR")


class SessionError(SSHError):
    """会话错误"""
    
    def __init__(self, message: str, session_id: str = ""):
        self.session_id = session_id
        super().__init__(message, "SESSION_ERROR")


class PromptDetectionError(SSHError):
    """提示符检测失败"""
    
    def __init__(self, output: str = "", expected_patterns: list = None):
        self.output = output
        self.expected_patterns = expected_patterns or []
        message = "Failed to detect prompt"
        if output:
            message += f" in output: {output[:100]}..."
        super().__init__(message, "PROMPT_DETECTION_ERROR")


class ConfigurationError(SSHError):
    """配置错误"""
    
    def __init__(self, message: str, config_key: str = ""):
        self.config_key = config_key
        super().__init__(message, "CONFIGURATION_ERROR")


class PoolError(SSHError):
    """连接池错误"""
    
    def __init__(self, message: str, pool_size: int = 0, max_size: int = 0):
        self.pool_size = pool_size
        self.max_size = max_size
        super().__init__(message, "POOL_ERROR")


class PoolExhaustedError(PoolError):
    """连接池耗尽错误"""
    
    def __init__(self, max_size: int):
        self.max_size = max_size
        super().__init__(
            f"Connection pool exhausted (max_size={max_size})",
            pool_size=max_size,
            max_size=max_size
        )


class PoolTimeoutError(PoolError):
    """连接池获取超时错误"""
    
    def __init__(self, timeout: float, max_size: int):
        self.timeout = timeout
        self.max_size = max_size
        super().__init__(
            f"Timeout waiting for connection from pool (timeout={timeout}s, max_size={max_size})",
            pool_size=max_size,
            max_size=max_size
        )


class ReceiverError(SSHError):
    """数据接收器错误"""
    
    def __init__(self, message: str, channel_id: str = ""):
        self.channel_id = channel_id
        super().__init__(message, "RECEIVER_ERROR")


class ValidationError(SSHError):
    """数据验证错误"""
    
    def __init__(self, message: str, field: str = ""):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR")
