"""异步 JSONL 记录器：负责在后台线程中落盘鞋垫的压力数据。"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from ..constants import COLS, ROWS


class DataLogger:
    """管理一次传感器采集会话的文件写入逻辑。"""

    def __init__(
        self,
        out_dir: Path | str = "records",
        *,
        flush_every: int = 32,
        queue_size: int = 512,
        flush_interval: float = 0.5,
    ) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._active = False
        self._start_time = 0.0
        self._stop_time = 0.0
        self._meta: Dict[str, Any] = {}
        self._session_id = ""
        self._file_path: Optional[Path] = None
        self._flush_every = max(1, int(flush_every))
        self._flush_interval = max(0.05, float(flush_interval))
        self._queue_size = max(self._flush_every * 2, int(queue_size))
        self._queue: Optional[queue.Queue] = None
        self._writer_thread: Optional[threading.Thread] = None
        self._writer_done = threading.Event()
        self._writer_exception: Optional[BaseException] = None
        self._sentinel = object()
        self._frame_count = 0
        self._last_frame_ts = 0.0
        self._end_recorded = False

    @property
    def active(self) -> bool:
        """指示当前是否正在有会话写入。"""
        return self._active

    def start_session(self, meta: Optional[Dict[str, Any]] = None) -> None:
        """开启新的记录会话，生成文件并启动写线程。"""
        with self._lock:
            if self._active:
                raise RuntimeError("已有会话正在运行，无法重复开启")
            self._writer_exception = None
            self._writer_done = threading.Event()
            self._start_time = time.time()
            self._stop_time = 0.0
            self._meta = dict(meta or {})
            self._session_id = time.strftime("session_%Y%m%d-%H%M%S", time.localtime(self._start_time))
            self._file_path = self.out_dir / f"{self._session_id}.jsonl"
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
            self._active = True

        writer_thread.start()
        self._submit_queue(
            {
                "type": "session_meta",
                "session_id": self._session_id,
                "session_start": self._start_time,
                "rows": ROWS,
                "cols": COLS,
                "meta": self._meta,
                "created_at": self._start_time,
            }
        )

    def append(self, side_is_left: bool, pmatrix: np.ndarray, ts: Optional[float] = None) -> None:
        """写入单帧压力矩阵；如果会话未开启则直接忽略。"""
        if pmatrix is None or getattr(pmatrix, "shape", None) != (ROWS, COLS):
            return
        if ts is None:
            ts = time.time()
        payload_matrix = np.asarray(pmatrix, dtype=np.float32)
        if payload_matrix.shape != (ROWS, COLS):
            return

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
            "side": 1 if side_is_left else 0,
            "rows": ROWS,
            "cols": COLS,
            "pressure": payload_matrix.tolist(),
        }
        self._submit_queue(payload)

    def stop_session(self, save: bool = True) -> Optional[Path]:
        """结束当前会话，可选择保留文件或清理文件。"""
        with self._lock:
            if not self._active:
                path = self._file_path
                if not save and path and path.exists():
                    path.unlink(missing_ok=True)
                    return None
                return path
            self._active = False
            self._stop_time = time.time()
        final_path = self._finalize()
        if save:
            return final_path
        if final_path and final_path.exists():
            final_path.unlink(missing_ok=True)
        return None

    def save(self, file_path: Optional[Path] = None) -> Path:
        """手动保存并可将文件移动到新的目录。"""
        with self._lock:
            if self._active:
                self._active = False
                if not self._stop_time:
                    self._stop_time = time.time()
        final_path = self._finalize()
        if file_path and file_path != final_path:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(final_path, file_path)
            with self._lock:
                self._file_path = file_path
            final_path = file_path
        return final_path

    def _finalize(self) -> Path:
        """等待写线程结束，并返回最终文件路径。"""
        with self._lock:
            file_path = self._file_path
            queue_ref = self._queue
            if file_path is None or queue_ref is None:
                return file_path or Path()
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
        return file_path

    def _ensure_writer_ok(self) -> None:
        """检查写线程是否抛出异常，若有异常则向调用者报告。"""
        if self._writer_exception is not None:
            raise RuntimeError("数据写线程发生异常") from self._writer_exception

    def _submit_queue(self, item: Any) -> None:
        """将任务放入写入队列，必要时阻塞等待。"""
        queue_ref = self._queue
        if queue_ref is None:
            raise RuntimeError("写入队列尚未就绪")
        self._ensure_writer_ok()
        try:
            queue_ref.put(item, block=False)
            return
        except queue.Full:
            pass
        queue_ref.put(item, timeout=self._flush_interval)

    def _writer_loop(self, file_path: Path, queue_ref: queue.Queue) -> None:
        """后台线程：批量取出数据并刷新到磁盘。"""
        buffer: list[dict[str, Any]] = []
        last_flush = time.monotonic()
        try:
            with file_path.open("w", encoding="utf-8") as handle:
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
        except BaseException as exc:
            self._writer_exception = exc
        finally:
            self._writer_done.set()

    def _write_batch(self, handle: Any, batch: list) -> None:
        """将一组 JSON 记录写入文件并立即刷新。"""
        for payload in batch:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
        handle.flush()
