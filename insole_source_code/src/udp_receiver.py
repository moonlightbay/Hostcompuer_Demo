import socket
import threading
from typing import Callable, Optional


class UdpReceiver:
    """
    简单的 UDP 监听器：在单独线程中阻塞接收，每次回调传入文本帧。
    回调签名: (frame: str, port: int) -> None
    """

    def __init__(self, local_port: int, on_frame: Callable[[str, int], None], bind_ip: str = "0.0.0.0"):
        self.local_port = local_port
        self.on_frame = on_frame
        self.bind_ip = bind_ip
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 允许端口快速复用
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.bind_ip, self.local_port))
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            if self._sock:
                self._sock.close()
        finally:
            self._sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(65536)
                frame = data.decode('utf-8', errors='ignore')
                if self.on_frame:
                    self.on_frame(frame, self.local_port)
            except OSError:
                # 套接字关闭时退出
                break
            except Exception:
                # 吞掉解析异常，继续接收
                continue
