"""解析鞋垫硬件通过 UDP 发来的文本帧，输出二维 AD 数组。"""

from __future__ import annotations

from typing import List

import numpy as np

from ..constants import COLS, MIN_VALID_AD, ROWS


def parse_frame_to_matrix(frame: str) -> np.ndarray:
    """解析一帧字符串数据，提取 AA..BB 段中的 34x10 AD 数组。"""
    if not frame:
        return np.zeros((ROWS, COLS), dtype=int)
    try:
        start = frame.find("AA")
        end = frame.find("BB")
        if start == -1 or end == -1 or end <= start:
            return np.zeros((ROWS, COLS), dtype=int)
        payload = frame[start + 2 : end]
        numbers: List[int] = []
        for token in payload.split(","):
            token = token.strip()
            if token and token.lstrip("-").isdigit():
                try:
                    numbers.append(int(token))
                except ValueError:
                    continue
        if len(numbers) < ROWS * COLS:
            numbers.extend([0] * (ROWS * COLS - len(numbers)))
        matrix = np.array(numbers[: ROWS * COLS], dtype=int).reshape(ROWS, COLS)
        matrix[matrix < MIN_VALID_AD] = 0
        return matrix
    except Exception:
        return np.zeros((ROWS, COLS), dtype=int)
