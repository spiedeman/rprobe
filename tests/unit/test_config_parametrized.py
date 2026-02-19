"""
参数化测试 - 减少重复代码

改进目标：将重复的测试改为参数化测试
"""

import pytest
from src import SSHConfig
from src.exceptions import ConfigurationError


class TestSSHConfigParametrized:
    """SSHConfig 参数化测试"""

    @pytest.mark.parametrize(
        "port",
        [
            22,  # SSH默认端口
            2222,  # 常用替代端口
            8080,  # HTTP代理端口
            443,  # HTTPS端口
            10022,  # 高位端口
            65535,  # 最大有效端口
            1,  # 最小有效端口
        ],
    )
    def test_valid_ports(self, port):
        """测试有效端口"""
        config = SSHConfig(host="example.com", username="user", password="pass", port=port)
        assert config.port == port

    @pytest.mark.parametrize(
        "port,expected_error",
        [
            (0, "端口号必须在1-65535之间"),
            (-1, "端口号必须在1-65535之间"),
            (-100, "端口号必须在1-65535之间"),
            (65536, "端口号必须在1-65535之间"),
            (100000, "端口号必须在1-65535之间"),
        ],
    )
    def test_invalid_ports(self, port, expected_error):
        """测试无效端口"""
        with pytest.raises(Exception, match=expected_error):
            SSHConfig(host="example.com", username="user", password="pass", port=port)


class TestSSHConfigValidationParametrized:
    """SSHConfig 验证参数化测试"""

    @pytest.mark.parametrize(
        "kwargs,expected_error,error_message",
        [
            # 空主机
            (
                {"host": "", "username": "user", "password": "pass"},
                ConfigurationError,
                "主机地址不能为空",
            ),
            # 空用户名
            (
                {"host": "example.com", "username": "", "password": "pass"},
                ConfigurationError,
                "用户名不能为空",
            ),
            # 同时指定密码和密钥
            (
                {
                    "host": "example.com",
                    "username": "user",
                    "password": "pass",
                    "key_filename": "/path/to/key",
                },
                ConfigurationError,
                "密码和密钥不能同时指定",
            ),
            # 无认证方式
            (
                {"host": "example.com", "username": "user"},
                ConfigurationError,
                "必须指定密码或密钥文件路径",
            ),
        ],
        ids=["empty_host", "empty_username", "both_auth", "no_auth"],
    )
    def test_validation_errors(self, kwargs, expected_error, error_message):
        """测试各种验证错误"""
        with pytest.raises(expected_error, match=error_message):
            SSHConfig(**kwargs)


class TestSSHConfigTimeoutParametrized:
    """超时配置参数化测试"""

    @pytest.mark.parametrize(
        "timeout,command_timeout",
        [
            (1.0, 10.0),
            (5.0, 30.0),
            (10.0, 60.0),
            (30.0, 300.0),
            (60.0, 600.0),
            (0.1, 1.0),  # 极短超时
        ],
    )
    def test_timeout_combinations(self, timeout, command_timeout):
        """测试不同超时组合"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass",
            timeout=timeout,
            command_timeout=command_timeout,
        )
        assert config.timeout == timeout
        assert config.command_timeout == command_timeout


class TestSSHConfigEncodingParametrized:
    """编码配置参数化测试"""

    @pytest.mark.parametrize(
        "encoding",
        [
            "utf-8",
            "gbk",
            "gb2312",
            "latin-1",
            "iso-8859-1",
            "cp1252",
        ],
    )
    def test_valid_encodings(self, encoding):
        """测试有效编码"""
        config = SSHConfig(host="example.com", username="user", password="pass", encoding=encoding)
        assert config.encoding == encoding


class TestSSHConfigRecvModeParametrized:
    """接收模式参数化测试"""

    @pytest.mark.parametrize(
        "recv_mode",
        [
            "auto",
            "select",
            "adaptive",
            "original",
        ],
    )
    def test_valid_recv_modes(self, recv_mode):
        """测试有效接收模式"""
        config = SSHConfig(
            host="example.com", username="user", password="pass", recv_mode=recv_mode
        )
        assert config.recv_mode == recv_mode


class TestSSHConfigMaxOutputSizeParametrized:
    """最大输出大小参数化测试"""

    @pytest.mark.parametrize(
        "max_output_size",
        [
            1024,  # 1KB
            10240,  # 10KB
            1024 * 1024,  # 1MB
            10 * 1024 * 1024,  # 10MB (默认)
            50 * 1024 * 1024,  # 50MB
            100 * 1024 * 1024,  # 100MB
        ],
    )
    def test_valid_max_output_sizes(self, max_output_size):
        """测试有效最大输出大小"""
        config = SSHConfig(
            host="example.com", username="user", password="pass", max_output_size=max_output_size
        )
        assert config.max_output_size == max_output_size


class TestSSHConfigStrRepresentationParametrized:
    """字符串表示参数化测试"""

    @pytest.mark.parametrize(
        "host,username,port,auth_method",
        [
            ("server1.com", "admin", 22, "password"),
            ("192.168.1.1", "root", 22, "password"),
            ("host.example.org", "deploy", 2222, "password"),
            ("10.0.0.1", "user", 10022, "password"),
        ],
    )
    def test_str_representation(self, host, username, port, auth_method):
        """测试配置字符串表示"""
        config = SSHConfig(host=host, username=username, password="pass123", port=port)
        str_repr = str(config)

        assert username in str_repr
        assert host in str_repr
        assert str(port) in str_repr
        assert auth_method in str_repr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
