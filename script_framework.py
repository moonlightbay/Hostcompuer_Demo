"""组织硬件模块运行的脚本框架示例。"""

from __future__ import annotations

import logging
from typing import Iterable, List

from bus.event_bus import EventBus
from bus.topics import Topics
from hardware.iHardware import IHardware
from utils.runtime import setup_basic_logging


def bootstrap_modules(bus: EventBus) -> List[IHardware]:
    """实例化并挂载所有硬件模块，返回模块列表。"""

    modules: List[IHardware] = []
    # 示例：
    # from hardware.insole import InsoleModule
    # from hardware.insole.runtime import load_config
    # config, config_root = load_config()
    # insole = InsoleModule(bus=bus, config=config, config_root=config_root)
    # insole.attach()
    # modules.append(insole)
    return modules


def register_observers(bus: EventBus) -> None:
    """在总线上注册必要的订阅者，例如日志、告警或 UI。"""

    log = logging.getLogger("framework.observer")

    def _status_logger(event: str, **payload) -> None:
        log.info("status event=%s payload=%s", event, payload)

    bus.subscribe(Topics.Hardware.Insole.STATUS, _status_logger)
    # 可以根据实际需求继续添加更多订阅者


def main() -> None:
    """框架入口：统一初始化日志、事件总线与模块。"""

    setup_basic_logging()
    log = logging.getLogger("framework")
    bus = EventBus()
    log.info("事件总线已创建，开始加载硬件模块")
    modules = bootstrap_modules(bus)
    register_observers(bus)
    log.info("已加载模块: %s", [module.name for module in modules])
    log.info("请在此处补充主循环逻辑、指令调度、资源清理等")

    try:
        # 开发者可在此实现主循环或阻塞逻辑
        log.info("框架示例运行完成（未实现主循环）")
    finally:
        shutdown_modules(modules)


def shutdown_modules(modules: Iterable[IHardware]) -> None:
    """确保所有模块在退出时执行清理。"""

    for module in modules:
        try:
            module.shutdown()
        except Exception as exc:  # pragma: no cover - 清理异常提示即可
            logging.getLogger("framework").error("模块 %s 关闭失败: %s", module.name, exc)


if __name__ == "__main__":
    main()
