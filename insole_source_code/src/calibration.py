from typing import Dict, Tuple, Optional, List
import csv
from .constants import ROWS, COLS

# 类型别名
Params = Dict[str, Tuple[float, float]]


def _fit_linear(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2 = sum(x * x for x in xs)
    den = n * sx2 - sx * sx
    if n < 2 or abs(den) < 1e-12:
        return 0.0, 0.0
    A = (n * sxy - sx * sy) / den
    B = (sy - A * sx) / n
    return A, B


def fit_calibration_from_csv(csv_path: str) -> Params:
    """
    读取 CSV，按点位字符串分组，对每组做线性拟合，返回 {key: (A,B)}。
    CSV 至少4列：第2列点位标识；第3列 AD；第4列 重量。
    首行视为表头跳过。
    """
    params: Params = {}
    groups: Dict[str, List[Tuple[float, float]]] = {}
    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
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
                wt = float(row[3].strip())
            except Exception:
                continue
            groups.setdefault(point, []).append((ad, wt))
    for key, samples in groups.items():
        if len(samples) < 2:
            continue
        xs = [a for a, _ in samples]
        ys = [w for _, w in samples]
        params[key] = _fit_linear(xs, ys)
    return params


def try_get_params(
    is_left: bool,
    row: int,
    col: int,
    left_params: Params,
    right_params: Params,
) -> Optional[Tuple[float, float]]:
    """
    根据左右脚与 (row,col) 尝试候选键名匹配，支持 0/1 基索引，及可选前缀“左脚/右脚”。
    """
    calib = left_params if is_left else right_params
    foot = "左脚" if is_left else "右脚"
    candidates = [
        f"{foot}{row}-{col}",
        f"{row}-{col}",
        f"{row+1}-{col+1}",
        f"{foot}{row+1}-{col+1}",
    ]
    for k in candidates:
        if k in calib:
            return calib[k]
    return None
