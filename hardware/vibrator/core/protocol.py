"""震动器蓝牙协议的基本封装。"""

from __future__ import annotations

from typing import Iterable

HEADER = 0x55
FOOTER = 0xAA
COMMAND_OFF = 0x00
COMMAND_ON = 0x01


def _checksum(command: int, payload: Iterable[int]) -> int:
    total = command + sum(payload)
    return total & 0xFF


def build_packet(command: int, intensity: int, duration_steps: int) -> bytes:
    """根据协议字段生成完整报文。"""

    if command not in (COMMAND_OFF, COMMAND_ON):
        raise ValueError(f"非法指令值: {command}")
    if not 0 <= intensity <= 100:
        raise ValueError("震动强度需位于 0~100")
    if not 0 <= duration_steps <= 255:
        raise ValueError("持续时间步进需位于 0~255")
    data = bytes([intensity, duration_steps])
    checksum = _checksum(command, data)
    return bytes([HEADER, command, *data, checksum, FOOTER])


__all__ = [
    "COMMAND_OFF",
    "COMMAND_ON",
    "build_packet",
]
