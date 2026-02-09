"""
配置管理器模块全面测试

提升 src/config/manager.py 的覆盖率到 90%+
"""
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.config.manager import SSHConfig, ConfigManager, load_config, YAML_AVAILABLE
from src.exceptions import ConfigurationError


class TestSSHConfig:
    """测试 SSHConfig 配置类"""
    
    def test_valid_password_config(self):
        """测试有效的密码认证配置"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass123"
        )
        assert config.host == "example.com"
        assert config.username == "user"
        assert config.password == "pass123"
        assert config.port == 22
        assert config.timeout == 30.0
        assert config.recv_mode == "auto"
    
    def test_valid_key_config(self):
        """测试有效的密钥认证配置"""
        # 创建临时密钥文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
            f.write("fake key content")
            key_path = f.name
        
        try:
            config = SSHConfig(
                host="example.com",
                username="user",
                key_filename=key_path
            )
            assert config.key_filename == key_path
            assert config.password is None
        finally:
            os.unlink(key_path)
    
    def test_config_with_all_fields(self):
        """测试所有字段的配置"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass",
            port=2222,
            key_password="keypass",
            timeout=60.0,
            command_timeout=600.0,
            max_output_size=20*1024*1024,
            encoding="gbk",
            recv_mode="select",
            recv_poll_interval=0.01
        )
        assert config.port == 2222
        assert config.timeout == 60.0
        assert config.encoding == "gbk"
        assert config.recv_mode == "select"
    
    def test_validation_empty_host(self):
        """测试空主机验证"""
        with pytest.raises(ConfigurationError, match="主机地址不能为空"):
            SSHConfig(host="", username="user", password="pass")
    
    def test_validation_empty_username(self):
        """测试空用户名验证"""
        with pytest.raises(ConfigurationError, match="用户名不能为空"):
            SSHConfig(host="example.com", username="", password="pass")
    
    def test_validation_both_auth_methods(self):
        """测试同时指定密码和密钥"""
        with pytest.raises(ConfigurationError, match="密码和密钥不能同时指定"):
            SSHConfig(
                host="example.com",
                username="user",
                password="pass",
                key_filename="/path/to/key"
            )
    
    def test_validation_no_auth_method(self):
        """测试不指定认证方式"""
        with pytest.raises(ConfigurationError, match="必须指定密码或密钥文件路径"):
            SSHConfig(host="example.com", username="user")
    
    def test_validation_invalid_port(self):
        """测试无效端口"""
        with pytest.raises(ConfigurationError, match="端口号必须在1-65535之间"):
            SSHConfig(host="example.com", username="user", password="pass", port=0)
        
        with pytest.raises(ConfigurationError, match="端口号必须在1-65535之间"):
            SSHConfig(host="example.com", username="user", password="pass", port=70000)
    
    def test_validation_missing_key_file(self):
        """测试密钥文件不存在"""
        with pytest.raises(ConfigurationError, match="密钥文件不存在"):
            SSHConfig(
                host="example.com",
                username="user",
                key_filename="/nonexistent/key"
            )
    
    def test_to_dict(self):
        """测试转换为字典"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass"
        )
        data = config.to_dict()
        assert data["host"] == "example.com"
        assert data["username"] == "user"
        assert data["port"] == 22
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "host": "example.com",
            "username": "user",
            "password": "pass",
            "invalid_field": "ignored"  # 应该被过滤
        }
        config = SSHConfig.from_dict(data)
        assert config.host == "example.com"
        assert not hasattr(config, "invalid_field")
    
    def test_copy_with(self):
        """测试复制并修改配置"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass"
        )
        new_config = config.copy_with(port=2222, timeout=60.0)
        
        assert new_config.host == "example.com"  # 未变
        assert new_config.port == 2222  # 已改
        assert new_config.timeout == 60.0  # 已改
    
    def test_str_representation(self):
        """测试字符串表示"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass"
        )
        assert "user@example.com:22" in str(config)
        assert "password" in str(config)


class TestConfigManager:
    """测试配置管理器"""
    
    def test_init(self):
        """测试初始化"""
        manager = ConfigManager()
        assert manager._data == {}
    
    def test_from_dict(self):
        """测试从字典加载"""
        manager = ConfigManager()
        manager.from_dict({"host": "test.com", "username": "admin"})
        
        assert manager._data["host"] == "test.com"
        assert manager._data["username"] == "admin"
        
        # 测试链式调用
        manager.from_dict({"port": 2222})
        assert manager._data["port"] == 2222
    
    def test_from_file_yaml(self):
        """测试从YAML文件加载"""
        if not YAML_AVAILABLE:
            pytest.skip("YAML not available")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("host: yaml-host.com\nusername: yamluser\npassword: yamlpass\nport: 2222\n")
            yaml_path = f.name
        
        try:
            manager = ConfigManager()
            manager.from_file(yaml_path)
            
            assert manager._data["host"] == "yaml-host.com"
            assert manager._data["port"] == 2222
        finally:
            os.unlink(yaml_path)
    
    def test_from_file_json(self):
        """测试从JSON文件加载"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "host": "json-host.com",
                "username": "jsonuser",
                "password": "jsonpass",
                "port": 3333
            }, f)
            json_path = f.name
        
        try:
            manager = ConfigManager()
            manager.from_file(json_path)
            
            assert manager._data["host"] == "json-host.com"
            assert manager._data["port"] == 3333
        finally:
            os.unlink(json_path)
    
    def test_from_file_not_exists(self):
        """测试文件不存在"""
        manager = ConfigManager()
        with pytest.raises(ConfigurationError, match="配置文件不存在"):
            manager.from_file("/nonexistent/config.yaml")
    
    def test_from_file_unsupported_format(self):
        """测试不支持的文件格式"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("invalid")
            txt_path = f.name
        
        try:
            manager = ConfigManager()
            with pytest.raises(ConfigurationError, match="不支持的配置文件格式"):
                manager.from_file(txt_path)
        finally:
            os.unlink(txt_path)
    
    def test_from_file_yaml_not_available(self):
        """测试YAML不可用"""
        if YAML_AVAILABLE:
            pytest.skip("YAML is available")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("host: test.com")
            yaml_path = f.name
        
        try:
            manager = ConfigManager()
            with pytest.raises(ConfigurationError, match="YAML support not available"):
                manager.from_file(yaml_path)
        finally:
            os.unlink(yaml_path)
    
    def test_from_file_invalid_content(self):
        """测试无效的文件内容"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            json_path = f.name
        
        try:
            manager = ConfigManager()
            with pytest.raises(ConfigurationError, match="加载配置文件失败"):
                manager.from_file(json_path)
        finally:
            os.unlink(json_path)
    
    def test_from_env(self):
        """测试从环境变量加载"""
        env_vars = {
            'REMOTE_SSH_HOST': 'env-host.com',
            'REMOTE_SSH_USERNAME': 'envuser',
            'REMOTE_SSH_PASSWORD': 'envpass',
            'REMOTE_SSH_PORT': '2222',
            'REMOTE_SSH_TIMEOUT': '60.0',
            'REMOTE_SSH_RECV_MODE': 'SELECT'
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            manager = ConfigManager()
            manager.from_env()
            
            assert manager._data["host"] == "env-host.com"
            assert manager._data["port"] == 2222  # 整数转换
            assert manager._data["timeout"] == 60.0  # 浮点数转换
            assert manager._data["recv_mode"] == "select"  # 小写转换
    
    def test_from_env_with_custom_prefix(self):
        """测试自定义前缀的环境变量"""
        env_vars = {
            'CUSTOM_HOST': 'custom.com',
            'CUSTOM_USERNAME': 'customuser',
            'CUSTOM_PASSWORD': 'custompass'
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            manager = ConfigManager()
            manager.from_env(prefix="CUSTOM_")
            
            assert manager._data["host"] == "custom.com"
    
    def test_set(self):
        """测试设置单个配置项"""
        manager = ConfigManager()
        manager.set("host", "test.com").set("port", 2222)
        
        assert manager._data["host"] == "test.com"
        assert manager._data["port"] == 2222
    
    def test_build(self):
        """测试构建配置对象"""
        manager = ConfigManager()
        manager.from_dict({
            "host": "test.com",
            "username": "admin",
            "password": "secret"
        })
        
        config = manager.build()
        assert isinstance(config, SSHConfig)
        assert config.host == "test.com"
    
    def test_load_from_file_classmethod(self):
        """测试类方法从文件加载"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "host": "file.com",
                "username": "fileuser",
                "password": "filepass"
            }, f)
            json_path = f.name
        
        try:
            config = ConfigManager.load_from_file(json_path)
            assert isinstance(config, SSHConfig)
            assert config.host == "file.com"
        finally:
            os.unlink(json_path)
    
    def test_load_from_env_classmethod(self):
        """测试类方法从环境变量加载"""
        env_vars = {
            'REMOTE_SSH_HOST': 'env.com',
            'REMOTE_SSH_USERNAME': 'envuser',
            'REMOTE_SSH_PASSWORD': 'envpass'
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = ConfigManager.load_from_env()
            assert isinstance(config, SSHConfig)
            assert config.host == "env.com"
    
    def test_create_default(self):
        """测试创建默认配置"""
        config = ConfigManager.create_default(
            host="default.com",
            username="defaultuser",
            password="defaultpass",
            port=2222
        )
        
        assert isinstance(config, SSHConfig)
        assert config.host == "default.com"
        assert config.port == 2222


class TestLoadConfig:
    """测试便捷加载函数"""
    
    def test_load_config_from_kwargs(self):
        """测试从kwargs加载配置"""
        config = load_config(
            use_env=False,
            host="kwarg.com",
            username="kwarguser",
            password="kwargpass"
        )
        
        assert config.host == "kwarg.com"
        assert config.username == "kwarguser"
    
    def test_load_config_from_file(self):
        """测试从文件加载配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "host": "file.com",
                "username": "fileuser",
                "password": "filepass"
            }, f)
            json_path = f.name
        
        try:
            config = load_config(file_path=json_path, use_env=False)
            assert config.host == "file.com"
        finally:
            os.unlink(json_path)
    
    def test_load_config_priority(self):
        """测试配置优先级"""
        # 文件配置
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "host": "file.com",
                "username": "fileuser",
                "password": "filepass",
                "port": 1111
            }, f)
            json_path = f.name
        
        # 环境变量配置
        env_vars = {
            'REMOTE_SSH_PORT': '2222'  # 覆盖文件的1111
        }
        
        try:
            with patch.dict(os.environ, env_vars, clear=False):
                # kwargs优先级最高，覆盖环境变量
                config = load_config(
                    file_path=json_path,
                    use_env=True,
                    port=3333  # 最高优先级
                )
                
                assert config.host == "file.com"  # 来自文件
                assert config.port == 3333  # 来自kwargs
        finally:
            os.unlink(json_path)
    
    def test_load_config_no_env(self):
        """测试不从环境变量加载"""
        env_vars = {
            'REMOTE_SSH_HOST': 'env.com',
            'REMOTE_SSH_USERNAME': 'envuser',
            'REMOTE_SSH_PASSWORD': 'envpass'
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_config(
                use_env=False,  # 禁用环境变量
                host="kwarg.com",
                username="kwarguser",
                password="kwargpass"
            )
            
            assert config.host == "kwarg.com"  # 不是env.com


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
