from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Generator, Optional, Tuple, List
import json
import numpy as np


@dataclass(frozen=True)
class SessionData:
    """
    读取 DataLogger 保存的 JSON Lines 会话文件后的统一数据结构。
    字段含义与 logger.py 中的写入格式保持一致。
    """
    t: np.ndarray            # (N,) float64 时间戳（秒）
    side: np.ndarray         # (N,) uint8  1=左, 0=右
    pm: np.ndarray           # (N, R, C) float32 压力矩阵
    rows: int
    cols: int
    start_time: float
    stop_time: float
    session_id: str
    meta: Dict[str, Any]


def load_session(file_path: str) -> SessionData:
    """
    按既定约定读取 JSON Lines 会话文件，返回 SessionData。
    如果传入 legacy `.npz` 文件，则抛出明确异常提示。
    """
    if file_path.lower().endswith(".npz"):
        raise RuntimeError("当前版本不再支持 .npz 会话文件，请使用新的 JSONL 保存格式重新采集数据。")

    frames_t: List[float] = []
    frames_side: List[int] = []
    frames_pm: List[np.ndarray] = []
    rows = 0
    cols = 0
    session_start = 0.0
    session_stop = 0.0
    session_id = ""
    meta: Dict[str, Any] = {}

    with open(file_path, "r", encoding="utf-8") as handle:
        for idx, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"解析 {file_path} 时在第 {idx} 行遇到无效 JSON: {exc}") from exc

            record_type = obj.get("type", "frame")
            if record_type == "session_meta":
                session_start = float(obj.get("session_start", session_start))
                session_id = str(obj.get("session_id", session_id))
                rows = int(obj.get("rows", rows) or rows)
                cols = int(obj.get("cols", cols) or cols)
                meta_obj = obj.get("meta", {})
                if isinstance(meta_obj, dict):
                    meta = meta_obj
                continue

            if record_type == "session_end":
                session_stop = float(obj.get("session_stop", session_stop))
                session_stop = session_stop or float(obj.get("last_frame_ts", session_stop))
                continue

            if record_type != "frame":
                # 未知类型，直接忽略
                continue

            ts = float(obj.get("frame_ts", 0.0))
            frames_t.append(ts)
            side_val = int(obj.get("side", 0))
            frames_side.append(side_val)
            pressure_payload = obj.get("pressure", [])
            pm = np.asarray(pressure_payload, dtype=np.float32)
            if pm.ndim == 1 and rows and cols and pm.size == rows * cols:
                pm = pm.reshape(rows, cols)
            elif pm.ndim != 2:
                if rows and cols:
                    pm = pm.reshape(rows, cols)  # type: ignore[arg-type]
                else:
                    raise RuntimeError(f"第 {idx} 行 pressure 数据无法还原为矩阵")

            if not rows or not cols:
                rows, cols = pm.shape

            frames_pm.append(pm)
            session_stop = max(session_stop, ts)

    if frames_pm:
        pm_array = np.stack(frames_pm, axis=0)
    else:
        pm_array = np.zeros((0, rows, cols), dtype=np.float32)

    t_array = np.asarray(frames_t, dtype=np.float64)
    side_array = np.asarray(frames_side, dtype=np.uint8)
    if session_stop == 0.0 and frames_t:
        session_stop = float(frames_t[-1])

    return SessionData(
        t=t_array,
        side=side_array,
        pm=pm_array,
        rows=int(rows),
        cols=int(cols),
        start_time=float(session_start),
        stop_time=float(session_stop),
        session_id=session_id,
        meta=meta,
    )


def iter_frames(sess: SessionData) -> Generator[Tuple[float, int, np.ndarray], None, None]:
    """逐帧迭代：yield (timestamp, side, pmatrix)。"""
    t = sess.t
    side = sess.side
    pm = sess.pm
    n = int(t.shape[0])
    for i in range(n):
        yield float(t[i]), int(side[i]), pm[i]


def frame_summary(sess: SessionData) -> Dict[str, np.ndarray]:
    """
    计算每帧的简单统计：total、nonzero、max。
    返回 dict: {"t", "side", "total", "nonzero", "max"}
    """
    t = sess.t
    side = sess.side
    pm = sess.pm
    # 防御性处理：空会话或形状异常
    if pm is None or pm.ndim != 3 or pm.shape[0] == 0:
        n = int(t.shape[0]) if hasattr(t, 'shape') else 0
        zeros = np.zeros((n,), dtype=np.float64)
        zeros_i = zeros.astype(np.int32)
        return {
            "t": np.asarray(t, dtype=np.float64) if hasattr(t, 'dtype') else zeros,
            "side": np.asarray(side, dtype=np.uint8) if hasattr(side, 'dtype') else zeros_i,
            "total": zeros,
            "nonzero": zeros_i,
            "max": zeros,
        }
    total = pm.reshape(pm.shape[0], -1).sum(axis=1)
    nonzero = (pm > 0).reshape(pm.shape[0], -1).sum(axis=1).astype(np.int32)
    maxv = pm.reshape(pm.shape[0], -1).max(axis=1) if pm.size > 0 else np.zeros_like(total)
    return {
        "t": np.asarray(t, dtype=np.float64),
        "side": np.asarray(side, dtype=np.uint8),
        "total": np.asarray(total, dtype=np.float64),
        "nonzero": np.asarray(nonzero, dtype=np.int32),
        "max": np.asarray(maxv, dtype=np.float64),
    }


def to_dataframe(sess: SessionData, flat: bool = False):
    """
    将 SessionData 转为 pandas.DataFrame（若 pandas 可用）。
    - flat=False：返回帧级摘要（t/side/total/nonzero/max）。
    - flat=True：返回展开后的逐点表，每帧 ROWS*COLS 行（大体量时请谨慎）。
    """
    try:
        import pandas as pd  # type: ignore
    except Exception as e:
        raise RuntimeError("pandas 未安装，无法导出 DataFrame。请先 pip install pandas") from e

    if not flat:
        s = frame_summary(sess)
        df = pd.DataFrame({k: s[k] for k in ["t", "side", "total", "nonzero", "max"]})
        return df

    # 展开逐点
    t = sess.t
    side = sess.side
    pm = sess.pm
    n, r, c = pm.shape
    # 构建 (n*r*c,) 的行
    ts = np.repeat(t, r * c)
    sides = np.repeat(side, r * c)
    rows = np.tile(np.repeat(np.arange(r, dtype=np.int32), c), n)
    cols = np.tile(np.tile(np.arange(c, dtype=np.int32), r), n)
    vals = pm.reshape(-1)
    df = pd.DataFrame({
        "t": ts,
        "side": sides,
        "row": rows,
        "col": cols,
        "pressure": vals,
    })
    return df


def print_session_summary(sess: SessionData) -> None:
    s = frame_summary(sess)
    n = int(s["t"].shape[0]) if hasattr(s["t"], 'shape') else 0
    duration = float(sess.stop_time - sess.start_time) if sess.stop_time and sess.start_time else 0.0
    left_frames = int((s["side"] == 1).sum()) if n else 0
    right_frames = int((s["side"] == 0).sum()) if n else 0
    print(f"session_id: {sess.session_id}")
    print(f"frames: {n}  left: {left_frames}  right: {right_frames}  duration: {duration:.2f}s")
    if n:
        print(f"total mean: {s['total'].mean():.3f}  max of max: {s['max'].max():.3f}")
