"""应用运行期的通用辅助工具。"""

from __future__ import annotations

import logging
from typing import Optional


def setup_basic_logging(level: int = logging.INFO, fmt: Optional[str] = None) -> None:
    """配置项目默认的日志输出格式与等级。"""

    format_string = fmt or "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=format_string)
