from __future__ import annotations
from typing import Optional, Dict, Any
import os
import time
import json
import threading
import queue
import numpy as np
from .constants import ROWS, COLS


class DataLogger:
    """
    线程安全的压力矩阵记录器（异步批量落盘）：
    - start_session(): 初始化会话并启动后台写线程
    - append(): 追加一帧 (timestamp, side, pressure_matrix)，写入缓存队列
    - stop_session(): 结束会话并等待写线程刷盘，可选择保留/删除文件
    - save(): 确保文件已落盘并（可选）重定位到指定路径

    数据以 JSON Lines 格式追加到单一文件：
    - 首行写入会话元信息（type=session_meta）
    - 每帧写入 type=frame，包含 session_start/session_id/side/pressure 等
    - 会话结束写入 type=session_end
    """

    def __init__(
        self,
        out_dir: str = "records",
        *,
        flush_every: int = 32,
        queue_size: int = 512,
        flush_interval: float = 0.5,
    ) -> None:
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._active = False
        self._start_time: float = 0.0
        self._stop_time: float = 0.0
        self._meta: Dict[str, Any] = {}
        self._session_id: str = ""
        self._file_path: Optional[str] = None
        self._flush_every = max(1, int(flush_every))
        self._flush_interval = max(0.05, float(flush_interval))
        self._queue_size = max(self._flush_every * 2, int(queue_size))
        self._queue: Optional[queue.Queue] = None
        self._writer_thread: Optional[threading.Thread] = None
        self._writer_done = threading.Event()
        self._writer_exception: Optional[BaseException] = None
        self._sentinel = object()
        self._frame_count: int = 0
        self._last_frame_ts: float = 0.0
        self._end_recorded: bool = False

    @property
    def active(self) -> bool:
        return self._active

    def start_session(self, meta: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            was_active = self._active
        if was_active:
            # 确保上一会话优雅收尾
            self.stop_session(save=True)

        ts = time.time()
        with self._lock:
            self._writer_exception = None
            self._writer_done = threading.Event()
            self._start_time = ts
            self._stop_time = 0.0
            self._meta = dict(meta or {})
            self._session_id = time.strftime("session_%Y%m%d-%H%M%S", time.localtime(ts))
            self._active = True
            self._file_path = os.path.join(self.out_dir, f"{self._session_id}.jsonl")
            self._frame_count = 0
            self._last_frame_ts = 0.0
            self._end_recorded = False
            self._queue = queue.Queue(maxsize=self._queue_size)
            queue_ref = self._queue
            writer_thread = threading.Thread(
                target=self._writer_loop,
                name=f"DataLoggerWriter-{self._session_id}",
                args=(self._file_path, queue_ref),
                daemon=True,
            )
            self._writer_thread = writer_thread

        writer_thread.start()
        # 写入会话元信息，供后续读取器解析
        self._submit_queue({
            "type": "session_meta",
            "session_id": self._session_id,
            "session_start": self._start_time,
            "rows": ROWS,
            "cols": COLS,
            "meta": self._meta,
            "created_at": ts,
        })

    def append(self, side_is_left: bool, pmatrix: np.ndarray, ts: Optional[float] = None) -> None:
        if pmatrix is None or getattr(pmatrix, "shape", None) != (ROWS, COLS):
            return
        if ts is None:
            ts = time.time()
        pm = np.asarray(pmatrix, dtype=np.float32)
        if pm.shape != (ROWS, COLS):
            return

        side_val = 1 if side_is_left else 0
        with self._lock:
            if not self._active:
                return
            frame_idx = self._frame_count
            self._frame_count += 1
            session_start = self._start_time
            session_id = self._session_id
            self._last_frame_ts = float(ts)

        payload = {
            "type": "frame",
            "session_id": session_id,
            "session_start": session_start,
            "frame_index": frame_idx,
            "frame_ts": float(ts),
            "side": side_val,
            "rows": ROWS,
            "cols": COLS,
            "pressure": pm.tolist(),
        }
        self._submit_queue(payload)

    def stop_session(self, save: bool = True) -> Optional[str]:
        with self._lock:
            if not self._active:
                file_path = self._file_path
                if not save and file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    return None
                return file_path
            self._active = False
            self._stop_time = time.time()
        if save:
            final_path = self._finalize()
            return final_path
        final_path = self._finalize()
        if final_path and os.path.exists(final_path):
            os.remove(final_path)
        return None

    def save(self, file_path: Optional[str] = None) -> str:
        with self._lock:
            if self._active:
                self._active = False
                if not self._stop_time:
                    self._stop_time = time.time()
        final_path = self._finalize()
        if file_path and file_path != final_path:
            target_dir = os.path.dirname(file_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            os.replace(final_path, file_path)
            with self._lock:
                self._file_path = file_path
            final_path = file_path
        return final_path

    def _finalize(self) -> str:
        with self._lock:
            file_path = self._file_path
            queue_ref = self._queue
            if not file_path or queue_ref is None:
                return file_path or ""
            if not self._end_recorded:
                payload = {
                    "type": "session_end",
                    "session_id": self._session_id,
                    "session_start": self._start_time,
                    "session_stop": self._stop_time or self._last_frame_ts,
                    "frames": self._frame_count,
                    "last_frame_ts": self._last_frame_ts,
                }
                self._end_recorded = True
            else:
                payload = None
            writer_thread = self._writer_thread

        if payload:
            self._submit_queue(payload)

        self._submit_queue(self._sentinel)
        if writer_thread:
            writer_thread.join()
        self._ensure_writer_ok()

        with self._lock:
            self._queue = None
            self._writer_thread = None
        return file_path or ""

    def _ensure_writer_ok(self) -> None:
        if self._writer_exception is not None:
            raise RuntimeError("DataLogger writer thread encountered an error") from self._writer_exception

    def _submit_queue(self, item: Any) -> None:
        queue_ref = self._queue
        if queue_ref is None:
            raise RuntimeError("DataLogger queue is not ready")
        self._ensure_writer_ok()
        try:
            queue_ref.put(item, block=False)
            return
        except queue.Full:
            pass
        try:
            queue_ref.put(item, timeout=self._flush_interval)
        except queue.Full as exc:
            raise RuntimeError("DataLogger queue is full; writer thread may be stalled") from exc

    def _writer_loop(self, file_path: str, queue_ref: queue.Queue) -> None:
        buffer = []
        last_flush = time.monotonic()
        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                while True:
                    timeout = max(0.0, self._flush_interval - (time.monotonic() - last_flush))
                    try:
                        item = queue_ref.get(timeout=timeout)
                    except queue.Empty:
                        item = None

                    if item is self._sentinel:
                        break
                    if item is not None:
                        buffer.append(item)

                    if buffer and (len(buffer) >= self._flush_every or item is None):
                        self._write_batch(handle, buffer)
                        buffer.clear()
                        last_flush = time.monotonic()

                if buffer:
                    self._write_batch(handle, buffer)
        except BaseException as exc:  # 捕获写线程异常，主线程后续会感知
            self._writer_exception = exc
        finally:
            self._writer_done.set()

    def _write_batch(self, handle: Any, batch: list) -> None:
        for payload in batch:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
        handle.flush()
