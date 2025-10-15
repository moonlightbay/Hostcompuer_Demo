"""对 UDP 收发能力的轻量封装，提供线程安全的发送与监听工具。"""

import socket
import threading
from typing import Callable, Optional


class UdpSender:
    """轻量 UDP 发送器，复用一个 socket，直接 sendto 到目标 IP/端口。"""

    def __init__(self, remote_ip: str, remote_port: int):
        """初始化发送器，记录目标地址并预创建 socket。"""

        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self._sock: Optional[socket.socket] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, message: str) -> None:
        """发送一条字符串消息，内部自动处理编码与 socket 重建。"""
        if not self._sock:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data = message.encode("utf-8", errors="ignore")
        try:
            self._sock.sendto(data, (self.remote_ip, self.remote_port))
        except Exception:
            # 发送异常忽略，避免打断主循环
            pass

    def close(self) -> None:
        """关闭内部 socket，释放系统资源。"""
        try:
            if self._sock:
                self._sock.close()
        finally:
            self._sock = None


class UdpReceiver:
    """
    简单的 UDP 监听器：在单独线程中阻塞接收，每次回调传入文本帧。
    回调签名: (frame: str, port: int) -> None
    """

    def __init__(self, local_port: int, on_frame: Callable[[str, int], None], bind_ip: str = "0.0.0.0"):
        """初始化监听器，指定本地端口、回调与绑定地址。"""

        self.local_port = local_port
        self.on_frame = on_frame
        self.bind_ip = bind_ip
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        """启动监听线程，若线程已存在则忽略。"""
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
        """停止监听线程，并等待线程退出。"""
        self._stop.set()
        try:
            if self._sock:
                self._sock.close()
        finally:
            self._sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        """线程入口：持续接收数据并触发回调。"""
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(65536)
                frame = data.decode("utf-8", errors="ignore")
                if self.on_frame:
                    self.on_frame(frame, self.local_port)
            except OSError:
                # 套接字关闭时退出
                break
            except Exception:
                # 吞掉解析异常，继续接收
                continue