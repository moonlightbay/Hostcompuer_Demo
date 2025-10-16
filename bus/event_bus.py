"""事件总线封装，提供统一的订阅、发布与调试入口。"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Set

from pubsub import pub

Listener = Callable[..., None]


@dataclass
class Subscription:
    """封装订阅句柄，便于在退出时解除监听。"""

    topic: str
    listener: Listener
    _bus: "EventBus"

    def unsubscribe(self) -> None:
        """从总线取消当前监听器。"""

        self._bus.unsubscribe(self)


class EventBus:
    """对 pypubsub 的轻量封装，统一入口便于依赖注入与调试。"""

    def __init__(self) -> None:
        self._listener_map: Dict[str, Set[Listener]] = {}

    def subscribe(self, topic: str, listener: Listener) -> Subscription:
        """订阅指定主题并记录监听器，返回可供释放的句柄。"""

        pub.subscribe(listener, topic)
        self._listener_map.setdefault(topic, set()).add(listener)
        return Subscription(topic=topic, listener=listener, _bus=self)

    def unsubscribe(self, subscription: Subscription) -> None:
        """取消之前的订阅，常用于模块卸载。"""

        pub.unsubscribe(subscription.listener, subscription.topic)
        listeners = self._listener_map.get(subscription.topic)
        if listeners is not None:
            listeners.discard(subscription.listener)
            if not listeners:
                self._listener_map.pop(subscription.topic, None)

    def publish(self, topic: str, **message: Any) -> None:
        """向主题广播事件，消息内容使用关键字参数传递。"""

        pub.sendMessage(topic, **message)

    def has_listeners(self, topic: str) -> bool:
        """检测是否存在监听者，便于调试或延迟初始化。"""

        listeners = self._listener_map.get(topic)
        if listeners:
            return True
        # 回退至 pubsub 内部状态，兼容直接使用 pub.subscribe 的情况
        topic_obj = pub.getDefaultTopicMgr().getTopic(topic, okIfNone=True)
        if topic_obj is None:
            return False
        if hasattr(topic_obj, "getListeners"):
            return bool(topic_obj.getListeners())
        return False

    def listener_count(self, topic: str) -> int:
        """返回当前已记录的监听器数量，用于监控订阅情况。"""

        if topic in self._listener_map:
            return len(self._listener_map[topic])
        topic_obj = pub.getDefaultTopicMgr().getTopic(topic, okIfNone=True)
        if topic_obj is None:
            return 0
        if hasattr(topic_obj, "getListeners"):
            return len(list(topic_obj.getListeners()))
        return 0

    def list_listeners(self, topic: str | None = None) -> Dict[str, List[str]]:
        """按主题列出监听器名称，辅助排查事件流转。"""

        topic_names = [topic] if topic else sorted(self._listener_map.keys())
        snapshot: Dict[str, List[str]] = {}
        for name in topic_names:
            listeners = self._listener_map.get(name, set())
            snapshot[name] = sorted(self._render_listener(listener) for listener in listeners)
        return snapshot

    def topics_snapshot(self) -> Dict[str, int]:
        """展示已知主题的监听器数量概览。"""

        return {topic: len(listeners) for topic, listeners in sorted(self._listener_map.items())}

    @staticmethod
    def _render_listener(listener: Listener) -> str:
        """将监听器转为可读名称。"""

        if inspect.ismethod(listener):
            self_obj = listener.__self__
            cls_name = type(self_obj).__name__
            func_name = listener.__func__.__name__
            return f"{cls_name}.{func_name}"
        if inspect.isfunction(listener):
            return listener.__qualname__
        return repr(listener)
