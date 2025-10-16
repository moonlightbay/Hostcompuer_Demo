"""鞋垫模块的调试脚本。"""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from typing import Any

from bus.bus import EventBus, Topics
from hardware.insole import InsoleModule
from hardware.insole.runtime import load_config, make_data_logger, make_status_logger
from utils.runtime import setup_basic_logging


def main() -> None:
    """示例流程：启动鞋垫模块、订阅事件并在固定时间后自动停止。"""

    setup_basic_logging()
    log = logging.getLogger("test.insole")
    bus = EventBus()
    config, config_root = load_config()
    insole = InsoleModule(bus=bus, config=config, config_root=config_root)
    insole.attach()

    status_sub = bus.subscribe(Topics.INSOLE_STATUS, make_status_logger())
    data_sub = bus.subscribe(Topics.INSOLE_DATA, make_data_logger())

    timer: threading.Timer | None = None

    def _shutdown(_: Any = None, __: Any = None) -> None:
        """处理退出逻辑：撤销订阅、通知模块停止并安全退出。"""

        nonlocal timer
        log.info("收到停止信号，准备退出测试脚本")
        status_sub.unsubscribe()
        data_sub.unsubscribe()
        if timer is not None:
            timer.cancel()
        bus.publish(Topics.INSOLE_COMMAND, action="stop")
        insole.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    log.info("发布启动指令，开始鞋垫数据采集测试")
    bus.publish(Topics.INSOLE_COMMAND, action="start")

    def delayed_stop() -> None:
        """定时触发的自动停止逻辑，便于演示收尾流程。"""

        log.info("自动停止计时器触发，准备停止鞋垫采集")
        bus.publish(Topics.INSOLE_COMMAND, action="stop")

    timer = threading.Timer(5.0, delayed_stop)
    timer.daemon = True
    timer.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        _shutdown()
    finally:
        if timer is not None:
            timer.cancel()


if __name__ == "__main__":
    main()
