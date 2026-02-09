"""
SSH 连接管理模块
提供 SSH 连接的生命周期管理
"""
import logging
from typing import Optional

import paramiko

from src.config.models import SSHConfig


logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    SSH 连接管理器
    
    负责建立、维护和关闭 SSH 连接。
    提供连接状态检查和自动重连功能。
    """
    
    def __init__(self, config: SSHConfig):
        """
        初始化连接管理器
        
        Args:
            config: SSH 连接配置
        """
        self._config = config
        self._client: Optional[paramiko.SSHClient] = None
        self._transport: Optional[paramiko.Transport] = None
        
    @property
    def is_connected(self) -> bool:
        """检查连接是否活跃"""
        if not self._transport:
            return False
        return self._transport.is_active()
    
    @property
    def transport(self) -> Optional[paramiko.Transport]:
        """获取传输层对象"""
        return self._transport
    
    def connect(self) -> None:
        """
        建立 SSH 连接
        
        Raises:
            paramiko.AuthenticationException: 认证失败
            paramiko.SSHException: SSH 连接错误
            TimeoutError: 连接超时
        """
        if self.is_connected:
            logger.debug(f"SSH 连接已存在: {self._config.host}")
            return
        
        logger.info(f"正在连接 SSH 服务器: {self._config.host}:{self._config.port}")
        
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_kwargs = {
            "hostname": self._config.host,
            "port": self._config.port,
            "username": self._config.username,
            "timeout": self._config.timeout,
            "allow_agent": False,
            "look_for_keys": False,
        }
        
        auth_method = "password" if self._config.password else "key"
        logger.debug(f"使用 {auth_method} 认证方式")
        
        if self._config.password:
            connect_kwargs["password"] = self._config.password
        elif self._config.key_filename:
            connect_kwargs["key_filename"] = self._config.key_filename
            if self._config.key_password:
                connect_kwargs["passphrase"] = self._config.key_password
        
        try:
            self._client.connect(**connect_kwargs)
            self._transport = self._client.get_transport()
            logger.info(f"SSH 连接成功: {self._config.host}")
        except paramiko.AuthenticationException as e:
            logger.error(f"SSH 认证失败: {self._config.host} - {e}")
            self._cleanup()
            raise
        except paramiko.SSHException as e:
            logger.error(f"SSH 连接错误: {self._config.host} - {e}")
            self._cleanup()
            raise
        except Exception as e:
            logger.error(f"SSH 连接异常: {self._config.host} - {e}")
            self._cleanup()
            raise
    
    def disconnect(self) -> None:
        """断开 SSH 连接"""
        if not self.is_connected:
            return
            
        logger.info(f"正在断开 SSH 连接: {self._config.host}")
        self._cleanup()
        logger.info(f"SSH 连接已断开: {self._config.host}")
    
    def _cleanup(self) -> None:
        """清理资源"""
        if self._transport:
            try:
                self._transport.close()
                logger.debug("Transport 已关闭")
            except Exception as e:
                logger.warning(f"关闭 Transport 时出错: {e}")
            self._transport = None
        
        if self._client:
            try:
                self._client.close()
                logger.debug("SSHClient 已关闭")
            except Exception as e:
                logger.warning(f"关闭 SSHClient 时出错: {e}")
            self._client = None
    
    def ensure_connected(self) -> None:
        """确保连接已建立，如未连接则自动连接"""
        if not self.is_connected:
            logger.debug("连接未建立，自动连接中...")
            self.connect()
    
    def open_channel(self, timeout: Optional[float] = None):
        """
        打开新的 SSH 通道
        
        Args:
            timeout: 超时时间
            
        Returns:
            paramiko.Channel: 新打开的通道
        """
        self.ensure_connected()
        return self._transport.open_session()
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
        return False
