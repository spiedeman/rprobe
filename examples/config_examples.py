#!/usr/bin/env python3
"""
配置加载示例

展示从不同来源加载SSH配置
"""
import os
from src import SSHConfig, load_config
from rprobe.config.manager import ConfigManager


def example_1_basic_config():
    """示例1: 基本配置创建"""
    print("=" * 60)
    print("示例1: 基本配置创建")
    print("=" * 60)
    
    # 方式1: 密码认证
    config1 = SSHConfig(
        host="server1.example.com",
        username="admin",
        password="secret123",
        port=22,
        timeout=30.0,
        command_timeout=300.0
    )
    print(f"✓ 密码认证配置: {config1}")
    
    # 方式2: 密钥认证
    config2 = SSHConfig(
        host="server2.example.com",
        username="deploy",
        key_filename="/home/user/.ssh/id_rsa",
        key_password="key_passphrase",  # 如果密钥有密码
        port=22
    )
    print(f"✓ 密钥认证配置: {config2}")
    
    # 方式3: 使用默认值
    config3 = SSHConfig(
        host="server3.example.com",
        username="user",
        password="pass"
        # port, timeout等使用默认值
    )
    print(f"✓ 默认配置: port={config3.port}, timeout={config3.timeout}")


def example_2_config_from_yaml():
    """示例2: 从YAML文件加载配置"""
    print("=" * 60)
    print("示例2: 从YAML文件加载")
    print("=" * 60)
    
    # 假设存在 config.yaml:
    # host: production.server.com
    # username: deploy
    # password: production_pass
    # port: 22
    # timeout: 60.0
    
    yaml_content = """
host: production.server.com
username: deploy
password: production_pass
port: 2222
timeout: 60.0
command_timeout: 600.0
"""
    
    # 创建临时YAML文件
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        yaml_file = f.name
    
    try:
        # 从YAML加载
        config = ConfigManager.load_from_file(yaml_file)
        print(f"✓ 从YAML加载: {config}")
        print(f"  Host: {config.host}")
        print(f"  Port: {config.port}")
        print(f"  Timeout: {config.timeout}")
    finally:
        import os
        os.unlink(yaml_file)


def example_3_config_from_json():
    """示例3: 从JSON文件加载配置"""
    print("=" * 60)
    print("示例3: 从JSON文件加载")
    print("=" * 60)
    
    json_content = """
{
    "host": "api.server.com",
    "username": "api_user",
    "password": "api_pass",
    "port": 22,
    "max_output_size": 20971520
}
"""
    
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(json_content)
        json_file = f.name
    
    try:
        config = ConfigManager.load_from_file(json_file)
        print(f"✓ 从JSON加载: {config}")
        print(f"  Max output: {config.max_output_size / 1024 / 1024}MB")
    finally:
        import os
        os.unlink(json_file)


def example_4_config_from_env():
    """示例4: 从环境变量加载"""
    print("=" * 60)
    print("示例4: 从环境变量加载")
    print("=" * 60)
    
    # 设置环境变量
    os.environ['REMOTE_SSH_HOST'] = 'env.server.com'
    os.environ['REMOTE_SSH_USERNAME'] = 'envuser'
    os.environ['REMOTE_SSH_PASSWORD'] = 'envpass'
    os.environ['REMOTE_SSH_PORT'] = '2222'
    
    try:
        # 从环境变量加载
        config = ConfigManager.load_from_env()
        print(f"✓ 从环境变量加载: {config}")
        print(f"  Host: {config.host}")
        print(f"  Port: {config.port}")
    finally:
        # 清理环境变量
        for key in ['REMOTE_SSH_HOST', 'REMOTE_SSH_USERNAME', 
                    'REMOTE_SSH_PASSWORD', 'REMOTE_SSH_PORT']:
            if key in os.environ:
                del os.environ[key]


def example_5_merged_config():
    """示例5: 合并配置（代码 > 环境变量 > 文件）"""
    print("=" * 60)
    print("示例5: 合并配置")
    print("=" * 60)
    
    # 创建基础配置文件
    json_content = '{"host": "file.server.com", "username": "fileuser", "password": "filepass"}'
    
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(json_content)
        config_file = f.name
    
    try:
        # 设置环境变量（会覆盖文件配置）
        os.environ['REMOTE_SSH_PORT'] = '2222'
        os.environ['REMOTE_SSH_TIMEOUT'] = '60'
        
        # 使用 load_config 合并配置
        # 优先级: 代码参数 > 环境变量 > 配置文件
        config = load_config(
            file_path=config_file,
            use_env=True,
            # 代码参数优先级最高
            username="codeuser",  # 覆盖文件中的 username
            command_timeout=600.0  # 添加新的配置
        )
        
        print(f"✓ 合并配置结果:")
        print(f"  Host: {config.host} (来自文件)")
        print(f"  Username: {config.username} (代码覆盖文件)")
        print(f"  Password: {'*' * len(config.password)} (来自文件)")
        print(f"  Port: {config.port} (来自环境变量)")
        print(f"  Timeout: {config.timeout} (来自环境变量)")
        print(f"  Command timeout: {config.command_timeout} (来自代码参数)")
        
    finally:
        os.unlink(config_file)
        for key in ['REMOTE_SSH_PORT', 'REMOTE_SSH_TIMEOUT']:
            if key in os.environ:
                del os.environ[key]


def example_6_config_validation():
    """示例6: 配置验证"""
    print("=" * 60)
    print("示例6: 配置验证")
    print("=" * 60)
    
    from rprobe.exceptions import ConfigurationError
    
    # 无效配置1: 空主机
    try:
        SSHConfig(host="", username="user", password="pass")
    except ConfigurationError as e:
        print(f"✓ 捕获错误 - 空主机: {e}")
    
    # 无效配置2: 同时指定密码和密钥
    try:
        SSHConfig(
            host="server.com",
            username="user",
            password="pass",
            key_filename="/path/to/key"
        )
    except ConfigurationError as e:
        print(f"✓ 捕获错误 - 双重认证: {e}")
    
    # 无效配置3: 没有认证方式
    try:
        SSHConfig(host="server.com", username="user")
    except ConfigurationError as e:
        print(f"✓ 捕获错误 - 无认证: {e}")
    
    # 无效配置4: 无效端口
    try:
        SSHConfig(
            host="server.com",
            username="user",
            password="pass",
            port=70000
        )
    except ConfigurationError as e:
        print(f"✓ 捕获错误 - 无效端口: {e}")
    
    print("\n✓ 所有验证正常工作")


if __name__ == "__main__":
    print("配置加载示例\n")
    
    # 取消注释要运行的示例
    # example_1_basic_config()
    # example_2_config_from_yaml()
    # example_3_config_from_json()
    # example_4_config_from_env()
    # example_5_merged_config()
    # example_6_config_validation()
    
    print("\n示例完成！请根据实际需求修改配置。")
