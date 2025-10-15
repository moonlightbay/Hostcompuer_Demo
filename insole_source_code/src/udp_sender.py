import socket
from typing import Optional


class UdpSender:
    """轻量 UDP 发送器，复用一个 socket，直接 sendto 到目标 IP/端口。"""

    def __init__(self, remote_ip: str, remote_port: int):
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self._sock: Optional[socket.socket] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, message: str) -> None:
        if not self._sock:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data = message.encode('utf-8', errors='ignore')
        try:
            self._sock.sendto(data, (self.remote_ip, self.remote_port))
        except Exception:
            # 发送异常忽略，避免打断主循环
            pass

    def close(self) -> None:
        try:
            if self._sock:
                self._sock.close()
        finally:
            self._sock = None
