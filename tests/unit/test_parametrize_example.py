"""
参数化测试示例

展示如何使用 @pytest.mark.parametrize 减少重复代码
"""

import pytest
from src import SSHConfig
from src.exceptions import ConfigurationError

# ==========================================
# 传统方式（重复代码多）
# ==========================================


class TestTraditional:
    """传统测试方式 - 重复代码"""

    def test_port_22(self):
        config = SSHConfig(host="test.com", username="user", password="pass", port=22)
        assert config.port == 22

    def test_port_2222(self):
        config = SSHConfig(host="test.com", username="user", password="pass", port=2222)
        assert config.port == 2222

    def test_port_8080(self):
        config = SSHConfig(host="test.com", username="user", password="pass", port=8080)
        assert config.port == 8080


# ==========================================
# 参数化方式（推荐）
# ==========================================


class TestParametrized:
    """参数化测试方式 - 简洁高效"""

    @pytest.mark.parametrize(
        "port",
        [
            22,  # SSH默认端口
            2222,  # 常用替代端口
            8080,  # HTTP代理端口
            443,  # HTTPS端口
            10022,  # 高位端口
            65535,  # 最大有效端口
        ],
    )
    def test_valid_ports(self, port):
        """测试有效端口"""
        config = SSHConfig(host="test.com", username="user", password="pass", port=port)
        assert config.port == port

    @pytest.mark.parametrize(
        "port,expected_error",
        [
            (0, "端口号必须在1-65535之间"),
            (-1, "端口号必须在1-65535之间"),
            (65536, "端口号必须在1-65535之间"),
            (100000, "端口号必须在1-65535之间"),
        ],
    )
    def test_invalid_ports(self, port, expected_error):
        """测试无效端口"""
        with pytest.raises(ConfigurationError, match=expected_error):
            SSHConfig(host="test.com", username="user", password="pass", port=port)


# ==========================================
# 多参数参数化
# ==========================================


class TestMultiParametrize:
    """多参数参数化测试"""

    @pytest.mark.parametrize(
        "host,username,expected_str",
        [
            ("server1.com", "admin", "admin@server1.com:22"),
            ("192.168.1.1", "root", "root@192.168.1.1:22"),
            ("host.example.org", "deploy", "deploy@host.example.org:22"),
        ],
    )
    def test_config_str_representation(self, host, username, expected_str):
        """测试配置字符串表示"""
        config = SSHConfig(host=host, username=username, password="pass")
        assert expected_str in str(config)

    @pytest.mark.parametrize(
        "timeout,command_timeout",
        [
            (10.0, 60.0),
            (30.0, 300.0),
            (60.0, 600.0),
            (5.0, 30.0),
        ],
    )
    def test_timeout_combinations(self, timeout, command_timeout):
        """测试不同超时组合"""
        config = SSHConfig(
            host="test.com",
            username="user",
            password="pass",
            timeout=timeout,
            command_timeout=command_timeout,
        )
        assert config.timeout == timeout
        assert config.command_timeout == command_timeout


# ==========================================
# 参数组合（笛卡尔积）
# ==========================================


class TestCartesianProduct:
    """笛卡尔积参数测试"""

    @pytest.mark.parametrize("recv_mode", ["auto", "select", "adaptive", "original"])
    @pytest.mark.parametrize("encoding", ["utf-8", "gbk", "latin-1"])
    def test_all_mode_encoding_combinations(self, recv_mode, encoding):
        """测试所有模式和编码的组合"""
        config = SSHConfig(
            host="test.com",
            username="user",
            password="pass",
            recv_mode=recv_mode,
            encoding=encoding,
        )
        assert config.recv_mode == recv_mode
        assert config.encoding == encoding


# ==========================================
# 动态参数生成
# ==========================================


def generate_port_range():
    """生成端口范围参数"""
    # 常用端口
    common_ports = [22, 80, 443, 8080, 8443]
    # SSH替代端口
    ssh_alt_ports = [2222, 22222, 10022]
    # 边界端口
    edge_ports = [1, 65535]

    return common_ports + ssh_alt_ports + edge_ports


class TestDynamicParams:
    """动态参数测试"""

    @pytest.mark.parametrize(
        "port", generate_port_range(), ids=lambda p: f"port_{p}"  # 自定义测试ID
    )
    def test_dynamic_ports(self, port):
        """测试动态生成的端口"""
        config = SSHConfig(host="test.com", username="user", password="pass", port=port)
        assert config.port == port


# ==========================================
# 参数化 + Fixture 组合
# ==========================================


@pytest.fixture
def base_config_dict():
    """基础配置字典"""
    return {"host": "test.example.com", "username": "testuser", "password": "testpass"}


class TestParametrizeWithFixture:
    """参数化和Fixture组合"""

    @pytest.mark.parametrize(
        "extra_config,expected_value",
        [
            ({"port": 2222}, 2222),
            ({"timeout": 60.0}, 60.0),
            ({"max_output_size": 52428800}, 52428800),
        ],
        ids=["custom_port", "custom_timeout", "custom_max_output"],
    )
    def test_config_with_extra_params(self, base_config_dict, extra_config, expected_value):
        """测试基础配置加额外参数"""
        config_dict = {**base_config_dict, **extra_config}
        config = SSHConfig(**config_dict)

        key = list(extra_config.keys())[0]
        assert getattr(config, key) == expected_value


# ==========================================
# 跳过特定参数
# ==========================================


class TestSkipSpecificParams:
    """跳过特定参数组合"""

    @pytest.mark.parametrize(
        "platform,mode",
        [
            ("linux", "select"),  # Linux支持select
            ("darwin", "select"),  # macOS支持select
            pytest.param(
                "windows",
                "select",  # Windows不支持select
                marks=pytest.mark.skip(reason="Windows不支持select模式"),
            ),
            ("windows", "adaptive"),  # Windows支持adaptive
            ("linux", "adaptive"),  # Linux也支持adaptive
        ],
    )
    def test_platform_specific_modes(self, platform, mode):
        """测试平台特定的模式"""
        # 测试逻辑
        pass


# ==========================================
# 条件参数
# ==========================================


@pytest.mark.skipif(not hasattr(SSHConfig, "recv_mode"), reason="SSHConfig不支持recv_mode属性")
class TestConditionalParams:
    """条件参数测试"""

    @pytest.mark.parametrize("recv_mode", ["auto", "select", "adaptive", "original"])
    def test_recv_modes_conditional(self, recv_mode):
        """条件性测试接收模式"""
        config = SSHConfig(host="test.com", username="user", password="pass", recv_mode=recv_mode)
        assert config.recv_mode == recv_mode


if __name__ == "__main__":
    # 运行参数化测试
    pytest.main([__file__, "-v", "--tb=short", "-k", "TestParametrized or TestMultiParametrize"])
