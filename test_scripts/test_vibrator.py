"""震动器模块的调试脚本。"""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    # 将项目根目录加入 sys.path，兼容直接运行该脚本的场景
    sys.path.insert(0, str(ROOT_DIR))

from bus.event_bus import EventBus
from bus.topics import Topics
from hardware.vibrator import VibratorModule
from hardware.vibrator.runtime import load_config, make_notification_logger, make_status_logger
from utils.runtime import setup_basic_logging


def main() -> None:
    setup_basic_logging()
    log = logging.getLogger("test.vibrator")
    bus = EventBus()
    config, _ = load_config()
    vibrator = VibratorModule(bus=bus, config=config)
    vibrator.attach()

    vib_topics = Topics.Hardware.Vibrator
    status_sub = bus.subscribe(vib_topics.STATUS, make_status_logger())
    notify_sub = bus.subscribe(vib_topics.NOTIFY, make_notification_logger())

    timer: threading.Timer | None = None

    def _shutdown(_: Any = None, __: Any = None) -> None:
        nonlocal timer
        log.info("收到停止信号，准备退出震动器测试")
        status_sub.unsubscribe()
        notify_sub.unsubscribe()
        if timer is not None:
            timer.cancel()
        bus.publish(vib_topics.COMMAND, action="stop")
        vibrator.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    log.info("发布开始指令，触发震动")
    bus.publish(vib_topics.COMMAND, action="start")

    def delayed_stop() -> None:
        log.info("自动停止计时器触发，发布停止指令")
        bus.publish(vib_topics.COMMAND, action="stop")

    timer = threading.Timer(3.0, delayed_stop)
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
