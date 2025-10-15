from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

from bus.bus import EventBus, Topics
from hardware.insole import InsoleConfig, InsoleModule


def _default_config_path() -> Path:
	"""返回鞋垫模块默认配置文件的绝对路径。"""

	root = Path(__file__).resolve().parent
	return root / "hardware" / "insole" / "config.json"


def load_config() -> tuple[InsoleConfig, Path]:
	"""读取配置文件，如果不存在则返回默认配置与目录。"""

	config_path = _default_config_path()
	if config_path.exists():
		config = InsoleConfig.from_file(config_path)
		return config, config_path.parent
	return InsoleConfig(), config_path.parent


def setup_logging() -> None:
	"""配置项目默认的日志格式与级别。"""

	logging.basicConfig(
		level=logging.INFO,
		format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
	)


def main() -> None:
	"""程序入口：初始化总线、读取配置并演示启动鞋垫模块。"""

	setup_logging()
	log = logging.getLogger("main")
	bus = EventBus()
	config, config_root = load_config()
	insole = InsoleModule(bus=bus, config=config, config_root=config_root)
	insole.attach()

	status_sub = bus.subscribe(Topics.INSOLE_STATUS, _make_status_logger())
	data_sub = bus.subscribe(Topics.INSOLE_DATA, _make_data_logger())

	timer: threading.Timer | None = None

	def _shutdown(_: Any = None, __: Any = None) -> None:
		"""处理信号退出：清理订阅并通知模块停止。"""

		nonlocal timer
		log.info("Shutdown requested")
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

	log.info("Publishing start command to insole module")
	bus.publish(Topics.INSOLE_COMMAND, action="start")

	def delayed_stop() -> None:
		"""自动停止回调：在指定时间后发布 stop 指令。"""

		log.info("Auto stop timer elapsed")
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


def _make_status_logger():
	"""创建状态主题的日志处理器，便于快速观察模块生命周期。"""

	log = logging.getLogger("insole.status")

	def _handler(event: str, payload: Any = None, **extra: Any) -> None:
		"""打印状态事件及其附加信息。"""

		combined = payload if extra == {} else {"payload": payload, **extra}
		log.info("event=%s payload=%s", event, combined)

	return _handler


def _make_data_logger():
	"""创建数据主题的日志处理器，快速查看压力帧摘要。"""

	log = logging.getLogger("insole.data")

	def _handler(frame: Dict[str, Any] | None = None, **_: Any) -> None:
		"""打印压力帧的侧别、总压力与有效点数量。"""

		if not frame:
			return
		stats = frame.get("stats", {})
		log.info(
			"#%s side=%s total=%.2f nonzero=%s",
			frame.get("frame_index"),
			frame.get("side"),
			stats.get("total_pressure", 0.0),
			stats.get("nonzero", 0),
		)

	return _handler


if __name__ == "__main__":
	main()
