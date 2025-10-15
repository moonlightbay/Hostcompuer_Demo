"""根据校准参数将 AD 矩阵转换为压力矩阵的算法。"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from .calibration import try_get_params
from ..constants import COLS, ROWS


def matrix_info(ad_matrix: Optional[np.ndarray]) -> tuple[int, float]:
    """统计矩阵有效点数量与最大值，便于监控硬件数据质量。"""
    if ad_matrix is None or getattr(ad_matrix, "shape", None) != (ROWS, COLS):
        return (0, 0.0)
    nonzero = int((ad_matrix > 0).sum())
    max_val = float(ad_matrix.max()) if nonzero else 0.0
    return (nonzero, max_val)


def _parse_key_to_rc(key: str) -> Optional[Tuple[int, int]]:
    """解析形如“左脚r-c”的键名为 0 基的 (row, col)。"""
    if not key:
        return None
    text = key.strip()
    if text.startswith("左脚"):
        text = text[2:]
    elif text.startswith("右脚"):
        text = text[2:]
    if "-" not in text:
        return None
    parts = text.split("-", 1)
    try:
        row = int(parts[0].strip())
        col = int(parts[1].strip())
    except Exception:
        return None
    if 0 <= row < ROWS and 0 <= col < COLS:
        return (row, col)
    if 1 <= row <= ROWS and 1 <= col <= COLS:
        return (row - 1, col - 1)
    return None


def _build_point_param_map(calib: Dict[str, Tuple[float, float]]) -> Dict[Tuple[int, int], Tuple[float, float]]:
    """将字符串键映射到 (row, col) 坐标，方便快速查找。"""
    result: Dict[Tuple[int, int], Tuple[float, float]] = {}
    for key, value in calib.items():
        rc = _parse_key_to_rc(key)
        if rc is None:
            continue
        result[rc] = value
    return result


def _predict_by_neighbors(
    row: int,
    col: int,
    ad_value: float,
    point_params: Dict[Tuple[int, int], Tuple[float, float]],
    k: int = 4,
    power: float = 2.0,
) -> float:
    """利用空间距离加权方式，推测缺少标定点的压力值。"""
    if ad_value <= 0 or not point_params:
        return 0.0
    neighbors: List[Tuple[float, float, float]] = []
    for (rr, cc), (a, b) in point_params.items():
        distance = math.hypot(rr - row, cc - col)
        neighbors.append((distance, a, b))
    if not neighbors:
        return 0.0
    neighbors.sort(key=lambda item: item[0])
    selected = neighbors[: max(1, min(k, len(neighbors)))]
    eps = 1e-6
    numerator = 0.0
    denominator = 0.0
    for distance, a, b in selected:
        weight = 1.0 / (pow(distance, power) + eps)
        estimate = a * ad_value + b
        numerator += weight * estimate
        denominator += weight
    if denominator <= 0:
        return 0.0
    value = numerator / denominator
    return float(value) if value > 0 else 0.0


def compute_pressure_matrix(
    ad_matrix: np.ndarray,
    is_left: bool,
    left_params: Dict[str, Tuple[float, float]],
    right_params: Dict[str, Tuple[float, float]],
) -> np.ndarray:
    """根据左右脚校准系数，将 AD 数据映射为压力矩阵。"""
    if ad_matrix is None or getattr(ad_matrix, "shape", None) != (ROWS, COLS):
        return np.zeros((ROWS, COLS), dtype=float)
    output = np.zeros((ROWS, COLS), dtype=float)
    calib = left_params if is_left else right_params
    point_params = _build_point_param_map(calib)
    for row in range(ROWS):
        for col in range(COLS):
            ad = int(ad_matrix[row, col])
            if ad <= 0:
                continue
            params = try_get_params(is_left, row, col, left_params, right_params)
            if params is None:
                predicted = _predict_by_neighbors(row, col, float(ad), point_params, k=4, power=2.0)
                if predicted > 0:
                    output[row, col] = predicted
                continue
            a, b = params
            value = a * ad + b
            if value > 0:
                output[row, col] = value
    return output
