"""
后台任务状态枚举和状态机
"""

from enum import Enum
from typing import Set, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import threading
import logging

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """
    后台任务状态枚举
    
    状态流转:
    PENDING -> RUNNING -> [COMPLETED | STOPPED | ERROR | TIMEOUT]
                    └-> STOPPING -> [STOPPED | ERROR]
    """
    PENDING = "pending"           # 待启动
    RUNNING = "running"           # 运行中
    STOPPING = "stopping"         # 停止中（发送SIGINT后）
    STOPPED = "stopped"           # 已停止
    COMPLETED = "completed"       # 正常完成
    ERROR = "error"               # 出错
    TIMEOUT = "timeout"           # 超时
    
    @property
    def is_terminal(self) -> bool:
        """是否为终态"""
        return self in {
            TaskStatus.COMPLETED, 
            TaskStatus.STOPPED, 
            TaskStatus.ERROR, 
            TaskStatus.TIMEOUT
        }
    
    @property
    def can_stop(self) -> bool:
        """是否可以停止"""
        return self == TaskStatus.RUNNING


# 状态流转规则
STATUS_TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.ERROR},
    TaskStatus.RUNNING: {
        TaskStatus.STOPPING, 
        TaskStatus.COMPLETED, 
        TaskStatus.ERROR, 
        TaskStatus.TIMEOUT
    },
    TaskStatus.STOPPING: {TaskStatus.STOPPED, TaskStatus.ERROR},
    TaskStatus.STOPPED: set(),
    TaskStatus.COMPLETED: set(),
    TaskStatus.ERROR: set(),
    TaskStatus.TIMEOUT: set(),
}


@dataclass
class StatusChangeEvent:
    """状态变更事件"""
    timestamp: datetime
    from_status: Optional[TaskStatus]
    to_status: TaskStatus
    reason: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class TaskStateMachine:
    """任务状态机"""
    
    def __init__(self, initial_status: TaskStatus = TaskStatus.PENDING):
        self._status = initial_status
        self._history: List[StatusChangeEvent] = []
        self._observers: List[Callable[[StatusChangeEvent], None]] = []
        self._lock = threading.Lock()
        
        self._record_change(None, initial_status, "initialized")
    
    @property
    def status(self) -> TaskStatus:
        return self._status
    
    def can_transition_to(self, new_status: TaskStatus) -> bool:
        """检查是否可以转换到目标状态"""
        return new_status in STATUS_TRANSITIONS.get(self._status, set())
    
    def transition_to(self, new_status: TaskStatus, reason: str = "", 
                      **metadata) -> bool:
        """转换状态"""
        with self._lock:
            if not self.can_transition_to(new_status):
                logger.warning(
                    f"无效状态转换: {self._status.value} -> {new_status.value}"
                )
                return False
            
            old_status = self._status
            self._status = new_status
            self._record_change(old_status, new_status, reason, metadata)
            
            # 通知观察者
            event = self._history[-1]
            for observer in self._observers:
                try:
                    observer(event)
                except Exception as e:
                    logger.error(f"状态观察者错误: {e}")
            
            return True
    
    def _record_change(self, from_status, to_status, reason, metadata=None):
        """记录状态变更"""
        event = StatusChangeEvent(
            timestamp=datetime.now(),
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            metadata=metadata or {}
        )
        self._history.append(event)
    
    def add_observer(self, callback: Callable[[StatusChangeEvent], None]):
        """添加状态变更观察者"""
        self._observers.append(callback)
    
    @property
    def history(self) -> List[StatusChangeEvent]:
        """获取状态历史"""
        return self._history.copy()
