"""
SSHConfig 配置类单元测试
"""
import pytest

from src.config.models import SSHConfig


class TestSSHConfig:
    """测试 SSHConfig 配置类"""

    def test_valid_password_config(self):
        """测试有效的密码认证配置"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass123",
            port=22,
            timeout=30.0,
            command_timeout=300.0,
            max_output_size=10 * 1024 * 1024,
        )
        
        assert config.host == "example.com"
        assert config.username == "user"
        assert config.password == "pass123"
        assert config.port == 22
        assert config.timeout == 30.0
        assert config.command_timeout == 300.0
        assert config.max_output_size == 10 * 1024 * 1024
        assert config.encoding == "utf-8"

    def test_valid_key_config(self):
        """测试有效的密钥认证配置"""
        config = SSHConfig(
            host="example.com",
            username="user",
            key_filename="/path/to/key",
            key_password="keypass",
        )
        
        assert config.key_filename == "/path/to/key"
        assert config.key_password == "keypass"
        assert config.password is None

    def test_default_values(self):
        """测试默认值"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass",
        )
        
        assert config.port == 22
        assert config.timeout == 30.0
        assert config.command_timeout == 300.0
        assert config.max_output_size == 10 * 1024 * 1024
        assert config.encoding == "utf-8"
        assert config.key_filename is None
        assert config.key_password is None

    def test_empty_host_raises_error(self):
        """测试空主机地址应抛出错误"""
        from src.exceptions import ConfigurationError
        with pytest.raises(ConfigurationError, match="主机地址不能为空"):
            SSHConfig(
                host="",
                username="user",
                password="pass",
            )

    def test_empty_username_raises_error(self):
        """测试空用户名应抛出错误"""
        from src.exceptions import ConfigurationError
        with pytest.raises(ConfigurationError, match="用户名不能为空"):
            SSHConfig(
                host="example.com",
                username="",
                password="pass",
            )

    def test_both_auth_methods_raises_error(self):
        """测试同时指定密码和密钥应抛出错误"""
        from src.exceptions import ConfigurationError
        with pytest.raises(ConfigurationError, match="密码和密钥不能同时指定"):
            SSHConfig(
                host="example.com",
                username="user",
                password="pass",
                key_filename="/path/to/key",
            )

    def test_no_auth_method_raises_error(self):
        """测试不指定认证方式应抛出错误"""
        from src.exceptions import ConfigurationError
        with pytest.raises(ConfigurationError, match="必须指定密码或密钥文件路径"):
            SSHConfig(
                host="example.com",
                username="user",
            )

    def test_config_equality(self):
        """测试配置对象相等性"""
        config1 = SSHConfig(host="example.com", username="user", password="pass")
        config2 = SSHConfig(host="example.com", username="user", password="pass")
        
        # dataclass 自动实现 __eq__
        assert config1 == config2
        
        config3 = SSHConfig(host="other.com", username="user", password="pass")
        assert config1 != config3

    def test_config_repr(self):
        """测试配置对象的字符串表示"""
        config = SSHConfig(host="example.com", username="user", password="pass")
        repr_str = repr(config)
        
        assert "SSHConfig" in repr_str
        assert "example.com" in repr_str
        assert "user" in repr_str
