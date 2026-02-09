"""
SSH 模块的数据模型
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class CommandResult:
    """
    命令执行结果
    
    Attributes:
        stdout: 标准输出内容
        stderr: 标准错误内容
        exit_code: 命令退出码（0 表示成功）
        execution_time: 执行耗时（秒）
        command: 执行的命令
    """
    
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    command: str
    
    @property
    def success(self) -> bool:
        """检查命令是否成功执行"""
        return self.exit_code == 0
    
    def __str__(self) -> str:
        """返回结果摘要"""
        status = "成功" if self.success else "失败"
        return (
            f"命令: {self.command}\n"
            f"状态: {status} (退出码: {self.exit_code})\n"
            f"耗时: {self.execution_time:.3f}秒\n"
            f"输出: {len(self.stdout)} 字符\n"
            f"错误: {len(self.stderr)} 字符"
        )
