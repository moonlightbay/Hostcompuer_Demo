from typing import Dict, Tuple, List, Optional
import numpy as np
import math
from .constants import ROWS, COLS
from .calibration import try_get_params

def matrix_info(ad_matrix) :
    # 计算ad矩阵非0元素数量和最大值
    if ad_matrix is None or getattr(ad_matrix, 'shape', None) != (ROWS, COLS):
        return 0, 0
    nonzero = int((ad_matrix > 0).sum())
    max_val = float(ad_matrix.max())
    return nonzero, max_val


def _parse_key_to_rc(key: str) -> Optional[Tuple[int, int]]:
    """
    解析校准字典中的键名 -> (row, col) 的 0 基坐标。
    支持以下形式：
    - "左脚r-c" / "右脚r-c"
    - "r-c"
    其中 r/c 可能为 0 基或 1 基，若为 1 基则转换为 0 基。
    超界则返回 None。
    """
    if not key:
        return None
    s = key.strip()
    if s.startswith("左脚"):
        s = s[2:]
    elif s.startswith("右脚"):
        s = s[2:]
    if '-' not in s:
        return None
    parts = s.split('-', 1)
    try:
        r = int(parts[0].strip())
        c = int(parts[1].strip())
    except Exception:
        return None
    # 两种索引制：优先 0 基合法判定，否则尝试转 1 基 -> 0 基
    if 0 <= r < ROWS and 0 <= c < COLS:
        rr, cc = r, c
    elif 1 <= r <= ROWS and 1 <= c <= COLS:
        rr, cc = r - 1, c - 1
    else:
        return None
    return (rr, cc)


def _build_point_param_map(calib: Dict[str, Tuple[float, float]]) -> Dict[Tuple[int, int], Tuple[float, float]]:
    """将 {key: (A,B)} 转换为 {(row,col): (A,B)}，无法解析的键跳过。"""
    out: Dict[Tuple[int, int], Tuple[float, float]] = {}
    for k, v in calib.items():
        rc = _parse_key_to_rc(k)
        if rc is None:
            continue
        out[rc] = v
    return out


def _predict_by_neighbors(
    r: int,
    c: int,
    ad: float,
    point_params: Dict[Tuple[int, int], Tuple[float, float]],
    k: int = 4,
    power: float = 2.0,
) -> float:
    """
    使用邻近已标定点的线性模型，对 (r,c) 的 AD 进行预测并加权平均。
    - 距离权重：w = 1 / (d^power + eps)
    - 取最近的 k 个点（若不足则全用）。
    返回预测压力（<0 则返回 0）。
    """
    if ad <= 0 or not point_params:
        return 0.0
    # 收集所有候选邻点
    entries: List[Tuple[float, float, float]] = []  # (distance, A, B)
    for (rr, cc), (A, B) in point_params.items():
        d = math.hypot(rr - r, cc - c)
        # 理论上 d 不可能为 0（否则该点有标定），但仍做保护
        entries.append((d, A, B))
    if not entries:
        return 0.0
    # 选取最近 k 个
    entries.sort(key=lambda x: x[0])
    selected = entries[: max(1, min(k, len(entries)))]
    eps = 1e-6
    num = 0.0
    den = 0.0
    for d, A, B in selected:
        w = 1.0 / (pow(d, power) + eps)
        y = A * ad + B
        num += w * y
        den += w
    if den <= 0:
        return 0.0
    y_hat = num / den
    return float(y_hat) if y_hat > 0 else 0.0

def compute_pressure_matrix(
    ad_matrix: np.ndarray,
    is_left: bool,
    left_params: Dict[str, Tuple[float, float]],
    right_params: Dict[str, Tuple[float, float]],
) -> np.ndarray:
    """
    将 34x10 AD 矩阵映射为压力矩阵：
    - 有匹配的标定参数则直接用 y = A*AD + B。
    - 若该点缺少标定，则使用基于空间近邻的插值：
      对最近 k 个已标定点的线性预测值进行距离加权平均，得到该点压力。
    - 负值统一置 0。
    """
    if ad_matrix is None or getattr(ad_matrix, 'shape', None) != (ROWS, COLS):
        return np.zeros((ROWS, COLS), dtype=float)
    out = np.zeros((ROWS, COLS), dtype=float)
    # 构建当前脚的已标定点映射，以便缺失点做插值
    calib = left_params if is_left else right_params
    point_params = _build_point_param_map(calib)
    for r in range(ROWS):
        for c in range(COLS):
            ad = int(ad_matrix[r, c])
            if ad <= 0:
                continue
            p = try_get_params(is_left, r, c, left_params, right_params)
            if p is None:
                # 缺失：使用邻点插值预测
                y = _predict_by_neighbors(r, c, float(ad), point_params, k=4, power=2.0)
                if y > 0:
                    out[r, c] = y
                continue
            A, B = p
            val = A * ad + B
            if val > 0:
                out[r, c] = val
    return out
