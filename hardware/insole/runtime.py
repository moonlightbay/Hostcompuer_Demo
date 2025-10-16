"""鞋垫模块运行期所需的辅助函数。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import InsoleConfig

LOG = logging.getLogger(__name__)


def default_config_path(app_root: Optional[Path] = None) -> Path:
    """返回鞋垫配置文件的默认路径。"""

    base = app_root or Path(__file__).resolve().parents[2]
    return base / "hardware" / "insole" / "config.json"


def load_config(config_path: Optional[Path] = None) -> Tuple[InsoleConfig, Path]:
    """读取鞋垫配置文件，若不存在则返回默认配置。"""

    path = (config_path or default_config_path()).resolve()
    config_dir = path.parent
    if path.exists():
        try:
            return InsoleConfig.from_file(path), config_dir
        except Exception as exc:  # pragma: no cover - 配置解析错误只在运行期出现
            LOG.error("读取鞋垫配置失败: %s", exc, exc_info=True)
    return InsoleConfig(), config_dir


def make_status_logger(logger_name: str = "insole.status"):
    """生成鞋垫状态事件的日志处理器。"""

    log = logging.getLogger(logger_name)

    def _handler(event: str, payload: Any = None, **extra: Any) -> None:
        combined: Any
        if not extra:
            combined = payload
        else:
            combined = {"payload": payload, **extra}
        log.info("event=%s payload=%s", event, combined)

    return _handler


def make_data_logger(logger_name: str = "insole.data"):
    """生成鞋垫压力帧的日志处理器。"""

    log = logging.getLogger(logger_name)

    def _handler(frame: Dict[str, Any] | None = None, **_: Any) -> None:
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
