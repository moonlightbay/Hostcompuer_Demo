"""震动器核心协议组件。"""

from .protocol import COMMAND_OFF, COMMAND_ON, build_packet

__all__ = [
    "COMMAND_OFF",
    "COMMAND_ON",
    "build_packet",
]
