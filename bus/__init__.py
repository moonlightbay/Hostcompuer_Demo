"""兼容模块：重新导出事件总线与主题定义。"""

from __future__ import annotations

from .event_bus import EventBus, Subscription
from .topics import TOPIC_REGISTRY, Topics, get_module_topics, register_module_topics

__all__ = [
    "EventBus",
    "Subscription",
    "Topics",
    "TOPIC_REGISTRY",
    "register_module_topics",
    "get_module_topics",
]


