"""鞋垫硬件的数据处理管线：解析帧、扣除噪声、计算压力并输出统计指标。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from .calibration import Params, fit_calibration_from_csv
from .parser import parse_frame_to_matrix
from .pressure import compute_pressure_matrix, matrix_info
from ..constants import COLS, MIN_VALID_AD, ROWS


@dataclass
class ProcessedFrame:
    """封装处理后的单帧数据，方便在总线上广播。"""

    timestamp: float
    port: int
    is_left: bool
    ad_matrix: np.ndarray
    pressure_matrix: np.ndarray
    stats: Dict[str, float | int]


class InsoleProcessor:
    """提供鞋垫数据处理的核心步骤，可重复复用在不同调度线程中。"""

    def __init__(
        self,
        *,
        left_csv: Optional[Path] = None,
        right_csv: Optional[Path] = None,
        ad_threshold: int = MIN_VALID_AD,
        left_port: int = 0,
        right_port: int = 0,
    ) -> None:
        self.left_params: Params = {}
        self.right_params: Params = {}
        self.ad_threshold = int(ad_threshold)
        self._left_port = int(left_port) if left_port else 0
        self._right_port = int(right_port) if right_port else 0
        self.reload_calibration(left_csv=left_csv, right_csv=right_csv)

    def reload_calibration(
        self,
        *,
        left_csv: Optional[Path] = None,
        right_csv: Optional[Path] = None,
    ) -> None:
        """重新加载校准文件，当 GUI 或配置更新时调用。"""
        self.left_params = {}
        self.right_params = {}
        if left_csv and left_csv.exists():
            self.left_params = fit_calibration_from_csv(left_csv)
        if right_csv and right_csv.exists():
            self.right_params = fit_calibration_from_csv(right_csv)

    def set_ports(self, left_port: int, right_port: int) -> None:
        """记录 UDP 监听端口，用于判断当前帧来自左脚还是右脚。"""
        self._left_port = int(left_port)
        self._right_port = int(right_port)

    def process(self, frame: str, port: int) -> Optional[ProcessedFrame]:
        """将原始字符串帧转换为结构化数据；异常时返回 None。"""
        timestamp = time.time()
        ad_matrix = parse_frame_to_matrix(frame)
        if ad_matrix.shape != (ROWS, COLS):
            return None
        filtered = ad_matrix.copy()
        threshold = self.ad_threshold
        if threshold > 0:
            filtered[filtered < threshold] = 0
        is_left = port == self._left_port
        pressure = compute_pressure_matrix(
            filtered,
            is_left=is_left,
            left_params=self.left_params,
            right_params=self.right_params,
        )
        nonzero, max_val = matrix_info(pressure)
        payload: Dict[str, float | int] = {
            "nonzero": int(nonzero),
            "max": float(max_val),
            "total_pressure": float(pressure.sum()),
        }
        return ProcessedFrame(
            timestamp=timestamp,
            port=port,
            is_left=is_left,
            ad_matrix=filtered,
            pressure_matrix=pressure,
            stats=payload,
        )
