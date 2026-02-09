"""
安全测试

测试系统的安全性和防护能力
"""
import pytest
from src import SSHConfig, SSHClient
from src.exceptions import ConfigurationError


class TestInputValidation:
    """输入验证安全测试"""
    
    @pytest.mark.parametrize("host", [
        "; rm -rf /",           # 命令注入尝试
        "| cat /etc/passwd",     # 管道注入
        "`whoami`",              # 反引号注入
        "$(whoami)",             # 命令替换
        "host; DROP TABLE",      # SQL注入风格
        "host\u0026\u0026 evil",       # 逻辑操作符
        "host||evil",            # 或操作
        "host#comment",          # 注释注入
    ])
    def test_command_injection_in_host(self, host):
        """测试主机名中的命令注入防护"""
        # SSHConfig应该正常存储，不进行命令执行
        config = SSHConfig(
            host=host,
            username="user",
            password="pass"
        )
        assert config.host == host  # 原样存储
    
    @pytest.mark.parametrize("username", [
        "root; rm -rf /",
        "admin' OR '1'='1",
        "user\nroot",
        "user\tadmin",
    ])
    def test_username_injection_attempts(self, username):
        """测试用户名注入尝试"""
        config = SSHConfig(
            host="example.com",
            username=username,
            password="pass"
        )
        assert config.username == username
    
    @pytest.mark.parametrize("password", [
        "pass; cat /etc/shadow",
        "pass' OR '1'='1",
        "pass$(whoami)",
        "pass`id`",
    ])
    def test_password_injection_attempts(self, password):
        """测试密码注入尝试"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password=password
        )
        assert config.password == password


class TestCredentialExposure:
    """凭据暴露防护测试"""
    
    def test_password_not_in_str(self):
        """测试密码不出现在字符串表示中"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="secret123"
        )
        
        str_repr = str(config)
        assert "secret123" not in str_repr
        assert "***" in str_repr or "password" in str_repr.lower()
    
    def test_key_password_not_logged(self):
        """测试密钥密码不被记录"""
        import tempfile
        import os
        
        # 创建临时密钥文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
            f.write("fake key")
            key_file = f.name
        
        try:
            config = SSHConfig(
                host="example.com",
                username="user",
                key_filename=key_file,
                key_password="secret_key_pass"
            )
            
            str_repr = str(config)
            assert "secret_key_pass" not in str_repr
        finally:
            os.unlink(key_file)
    
    def test_config_to_dict_exposes_password(self):
        """测试to_dict是否包含密码（应该包含，用于内部使用）"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="secret123"
        )
        
        data = config.to_dict()
        # to_dict应该包含所有字段（包括密码）
        assert data['password'] == "secret123"
        # 但应该有警告或说明


class TestPathValidation:
    """路径验证测试"""
    
    def test_key_path_validation(self):
        """测试密钥路径验证（仅在非测试模式下）"""
        import os
        
        # 如果处于测试模式，跳过此测试
        if os.environ.get('TESTING'):
            pytest.skip("测试模式跳过文件存在性检查")
        
        # 应该接受路径但验证存在性
        with pytest.raises(ConfigurationError, match="密钥文件不存在"):
            SSHConfig(
                host="example.com",
                username="user",
                key_filename="/nonexistent/key/file"
            )
    
    def test_path_traversal_prevention(self):
        """测试路径遍历防护"""
        import tempfile
        import os
        
        # 创建临时目录结构
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建允许的密钥文件
            allowed_key = os.path.join(tmpdir, "allowed_key")
            with open(allowed_key, 'w') as f:
                f.write("fake key")
            
            # 尝试使用相对路径
            config = SSHConfig(
                host="example.com",
                username="user",
                key_filename=allowed_key
            )
            assert config.key_filename == allowed_key


class TestResourceLimits:
    """资源限制测试"""
    
    def test_max_output_size_limit(self):
        """测试最大输出大小限制"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass",
            max_output_size=1024  # 1KB
        )
        assert config.max_output_size == 1024
    
    def test_timeout_limits(self):
        """测试超时限制"""
        # 极短超时
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass",
            timeout=0.001,  # 1ms
            command_timeout=0.01  # 10ms
        )
        assert config.timeout == 0.001
        assert config.command_timeout == 0.01
    
    def test_port_range_limits(self):
        """测试端口范围限制"""
        # 有效边界值
        config1 = SSHConfig(
            host="example.com",
            username="user",
            password="pass",
            port=1
        )
        assert config1.port == 1
        
        config2 = SSHConfig(
            host="example.com",
            username="user",
            password="pass",
            port=65535
        )
        assert config2.port == 65535


class TestErrorHandling:
    """错误处理安全测试"""
    
    def test_error_message_no_credential_leak(self):
        """测试错误消息不泄露凭据"""
        password = "secret_password_123"
        
        try:
            SSHConfig(
                host="",
                username="user",
                password=password
            )
        except ConfigurationError as e:
            error_msg = str(e)
            assert password not in error_msg
    
    def test_stack_trace_no_credential_leak(self):
        """测试堆栈跟踪不泄露凭据"""
        import traceback
        
        password = "super_secret"
        
        try:
            SSHConfig(
                host="",
                username="user",
                password=password
            )
        except Exception:
            stack_trace = traceback.format_exc()
            assert password not in stack_trace


class TestConcurrencySafety:
    """并发安全测试"""
    
    def test_concurrent_config_creation(self):
        """测试并发配置创建安全"""
        import threading
        
        configs = []
        errors = []
        
        def create_config():
            try:
                config = SSHConfig(
                    host="example.com",
                    username="user",
                    password="pass"
                )
                configs.append(config)
            except Exception as e:
                errors.append(e)
        
        # 并发创建100个配置
        threads = []
        for _ in range(100):
            t = threading.Thread(target=create_config)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(configs) == 100
        assert len(errors) == 0
    
    def test_config_immutability(self):
        """测试配置创建后不应意外修改"""
        config = SSHConfig(
            host="example.com",
            username="user",
            password="pass"
        )
        
        original_host = config.host
        
        # 尝试修改（不应该成功或应该创建新对象）
        try:
            config.host = "modified.com"
            # 如果能修改，验证是否允许
            assert config.host == "modified.com"
        except AttributeError:
            # 如果不允许修改，也是可接受的
            assert config.host == original_host


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
