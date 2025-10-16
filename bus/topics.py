"""集中管理事件主题名称及模块级元数据。"""

from __future__ import annotations

from typing import Dict, Mapping

ModuleTopicDetails = Dict[str, str]
ModuleTopicProfile = Dict[str, ModuleTopicDetails]


def _copy_mapping(mapping: Mapping[str, str] | None) -> ModuleTopicDetails:
    return dict(mapping) if mapping else {}


class Topics:
    """按领域分组的事件主题常量，避免魔法字符串散落各处。"""

    class Hardware:
        ROOT = "hardware"

        class Insole:
            COMMAND = "hardware.insole.command"
            STATUS = "hardware.insole.status"
            DATA = "hardware.insole.data"

    class System:
        CONTROL = "system.control"
        SHUTDOWN = "system.shutdown"


TOPIC_REGISTRY: Dict[str, ModuleTopicProfile] = {}


def register_module_topics(
    module_name: str,
    *,
    publish: Mapping[str, str] | None = None,
    subscribe: Mapping[str, str] | None = None,
) -> None:
    """记录模块发布与订阅的主题，便于文档化与调试。"""

    TOPIC_REGISTRY[module_name] = {
        "publish": _copy_mapping(publish),
        "subscribe": _copy_mapping(subscribe),
    }


def get_module_topics(module_name: str) -> ModuleTopicProfile | None:
    """返回已登记的模块主题信息。"""

    return TOPIC_REGISTRY.get(module_name)
