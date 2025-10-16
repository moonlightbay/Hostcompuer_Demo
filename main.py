from __future__ import annotations

import logging

from bus.bus import EventBus
from utils.runtime import setup_basic_logging


def main() -> None:
	"""正式的程序入口，占位示例。"""

	setup_basic_logging()
	log = logging.getLogger("app")
	bus = EventBus()
	log.info("主程序入口已启动，当前尚未加载具体硬件模块。")
	log.info("请参考 script_framework.py 或 test_insole.py 完成业务初始化。")
	log.debug("事件总线实例: %s", bus)


if __name__ == "__main__":
	main()
