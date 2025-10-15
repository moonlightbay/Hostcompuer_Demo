from typing import Optional, List
import numpy as np
from .constants import ROWS, COLS, MIN_VALID_AD


def parse_frame_to_matrix(frame: str) -> np.ndarray:
    """
    解析 UDP 文本帧中 AA..BB 段的 340 个整数，转换为 34x10 AD 矩阵；<120 置 0。
    若 AA/BB 缺失或数量不足，返回全零矩阵。
    """
    if not frame:
        return np.zeros((ROWS, COLS), dtype=int)
    try:
        a = frame.find("AA")
        b = frame.find("BB")
        if a == -1 or b == -1 or b <= a:
            return np.zeros((ROWS, COLS), dtype=int)
        payload = frame[a + 2 : b]
        nums: List[int] = []
        for tok in payload.split(','):
            t = tok.strip()
            # 允许负号；非数字跳过
            if t and (t.lstrip('-').isdigit()):
                try:
                    nums.append(int(t))
                except ValueError:
                    pass
        if len(nums) < ROWS * COLS:
            nums += [0] * (ROWS * COLS - len(nums))
        arr = np.array(nums[: ROWS * COLS], dtype=int).reshape(ROWS, COLS)
        arr[arr < MIN_VALID_AD] = 0
        return arr
    except Exception:
        return np.zeros((ROWS, COLS), dtype=int)


def subtract_baseline(ad: np.ndarray, baseline: Optional[np.ndarray]) -> np.ndarray:
    """逐点 max(0, ad - baseline)。baseline 为空或形状不符则返回原值。"""
    if baseline is None or baseline.shape != (ROWS, COLS):
        return ad
    out = ad - baseline
    out[out < 0] = 0
    return out

