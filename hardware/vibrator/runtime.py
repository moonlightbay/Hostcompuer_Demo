"""震动器模块运行期辅助方法。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import VibratorConfig

LOG = logging.getLogger(__name__)


def default_config_path(app_root: Optional[Path] = None) -> Path:
    base = app_root or Path(__file__).resolve().parents[2]
    return base / "hardware" / "vibrator" / "config.json"


def load_config(config_path: Optional[Path] = None) -> Tuple[VibratorConfig, Path]:
    path = (config_path or default_config_path()).resolve()
    config_dir = path.parent
    config = VibratorConfig.from_file(path)
    return config, config_dir


def make_status_logger(logger_name: str = "vibrator.status"):
    log = logging.getLogger(logger_name)

    def _handler(event: str, payload: Any = None, **extra: Any) -> None:
        merged: Dict[str, Any] = {}
        if payload is not None:
            merged["payload"] = payload
        if extra:
            merged.update(extra)
        log.info("event=%s details=%s", event, merged or None)

    return _handler


def make_notification_logger(logger_name: str = "vibrator.notify"):
    log = logging.getLogger(logger_name)

    def _handler(event: str, payload: Dict[str, Any] | None = None, **_: Any) -> None:
        if not payload:
            return
        log.info("event=%s hex=%s", event, payload.get("hex"))

    return _handler
