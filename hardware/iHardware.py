"""硬件模块的抽象基类，约束所有设备适配器的生命周期接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, List

from bus.event_bus import EventBus


class IHardware(ABC):
    """所有硬件模块需要遵循的统一接口。"""

    topics: ClassVar[Dict[str, List[str]]] = {"publish": [], "subscribe": []}

    def __init__(self, name: str, bus: EventBus):
        self.name = name
        self.bus = bus
        self.connected = False

    @abstractmethod
    def attach(self) -> None:
        """注册事件监听并申请所需资源。"""

    @abstractmethod
    def detach(self) -> None:
        """取消订阅并释放资源。"""

    @abstractmethod
    def handle_command(self, action: str, payload: dict[str, Any] | None = None) -> None:
        """响应总线发来的控制指令。"""

    @abstractmethod
    def shutdown(self) -> None:
        """在进程退出前执行最终清理。"""

    def publish(self, topic: str, **message: Any) -> None:
        """向总线发布消息，供其他模块订阅使用。"""
        self.bus.publish(topic, **message)

    @classmethod
    def describe_topics(cls) -> Dict[str, List[str]]:
        """返回模块声明的主题信息，便于统一展示。"""

        return {
            "publish": list(cls.topics.get("publish", [])),
            "subscribe": list(cls.topics.get("subscribe", [])),
        }

