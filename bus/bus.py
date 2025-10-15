"""应用级事件总线封装，统一管理所有 pubsub 主题。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pubsub import pub


class Topics:
    """集中定义的主题名称，避免各模块自行拼接字符串。"""

    HARDWARE_ROOT = "hardware"
    INSOLE_COMMAND = "hardware.insole.command"
    INSOLE_STATUS = "hardware.insole.status"
    INSOLE_DATA = "hardware.insole.data"
    SYSTEM_CONTROL = "system.control"
    SYSTEM_SHUTDOWN = "system.shutdown"


Listener = Callable[..., None]


@dataclass
class Subscription:
    """封装订阅句柄，方便在退出时解除监听。"""

    topic: str
    listener: Listener

    def unsubscribe(self) -> None:
        """从总线取消订阅当前监听器。"""
        pub.unsubscribe(self.listener, self.topic)


class EventBus:
    """对 pypubsub 的轻量封装，统一入口便于依赖注入。"""

    def subscribe(self, topic: str, listener: Listener) -> Subscription:
        """订阅指定主题，返回可供释放的句柄。"""
        pub.subscribe(listener, topic)
        return Subscription(topic=topic, listener=listener)

    def unsubscribe(self, subscription: Subscription) -> None:
        """取消之前的订阅，常用于模块卸载。"""
        pub.unsubscribe(subscription.listener, subscription.topic)

    def publish(self, topic: str, **message: Any) -> None:
        """向主题广播事件，消息内容使用关键字参数传递。"""
        pub.sendMessage(topic, **message)

    def has_listeners(self, topic: str) -> bool:
        """检测是否存在监听者，便于调试或延迟初始化。"""
        return pub.getDefaultTopicMgr().getTopic(topic, okIfNone=True) is not None


