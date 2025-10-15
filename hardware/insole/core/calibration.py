"""校准参数相关的核心工具，负责将传感器的 AD 数值映射为线性压力系数。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..constants import COLS, ROWS

Params = Dict[str, Tuple[float, float]]


def _fit_linear(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    """使用最小二乘法拟合 y = a * x + b 的线性模型，返回 (a, b)。"""
    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2 = sum(x * x for x in xs)
    den = n * sx2 - sx * sx
    if n < 2 or abs(den) < 1e-12:
        return 0.0, 0.0
    a = (n * sxy - sx * sy) / den
    b = (sy - a * sx) / n
    return float(a), float(b)


def fit_calibration_from_csv(csv_path: Path) -> Params:
    """读取标定 CSV 文件，返回每个传感器点位对应的线性系数映射表。"""
    params: Params = {}
    groups: Dict[str, List[Tuple[float, float]]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header_skipped = False
        for row in reader:
            if not header_skipped:
                header_skipped = True
                continue
            if len(row) < 4:
                continue
            point = row[1].strip()
            try:
                ad = float(row[2].strip())
                weight = float(row[3].strip())
            except Exception:
                continue
            groups.setdefault(point, []).append((ad, weight))
    for key, samples in groups.items():
        if len(samples) < 2:
            continue
        xs = [ad for ad, _ in samples]
        ys = [weight for _, weight in samples]
        params[key] = _fit_linear(xs, ys)
    return params


def try_get_params(
    is_left: bool,
    row: int,
    col: int,
    left_params: Params,
    right_params: Params,
) -> Optional[Tuple[float, float]]:
    """根据左右脚与传感器行列号，查找对应的线性系数 (a, b)。"""
    calib = left_params if is_left else right_params
    foot = "左脚" if is_left else "右脚"
    candidates = [
        f"{foot}{row}-{col}",
        f"{row}-{col}",
        f"{row+1}-{col+1}",
        f"{foot}{row+1}-{col+1}",
    ]
    for key in candidates:
        if key in calib:
            return calib[key]
    return None
