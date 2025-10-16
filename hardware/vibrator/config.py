"""震动器模块的配置定义与解析工具。"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Optional

from utils.communication.ble import BleDeviceProfile

LOG = logging.getLogger(__name__)


def _clamp(value: int, *, lower: int, upper: int) -> int:
    return max(lower, min(upper, int(value)))


def _duration_to_steps(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return 0
    if duration <= 0:
        return 0
    steps = math.ceil(duration / 50.0)
    return _clamp(steps, lower=0, upper=255)


@dataclass
class RetryPolicy:
    """描述重试策略。"""

    attempts: int = 3
    interval_seconds: float = 0.5

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | None, fallback: "RetryPolicy") -> "RetryPolicy":
        if not payload:
            return fallback
        return cls(
            attempts=_clamp(payload.get("attempts", fallback.attempts), lower=1, upper=10),
            interval_seconds=float(payload.get("interval_seconds", fallback.interval_seconds)),
        )


@dataclass
class BleConnectionConfig:
    """BLE 连接配置，包含地址与特征值 UUID。"""

    address: str
    service_uuid: str
    write_characteristic: str
    notify_characteristic: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | None, fallback: "BleConnectionConfig") -> "BleConnectionConfig":
        payload = payload or {}
        return cls(
            address=str(payload.get("address", fallback.address)),
            service_uuid=str(payload.get("service_uuid", fallback.service_uuid)),
            write_characteristic=str(payload.get("write_characteristic", fallback.write_characteristic)),
            notify_characteristic=payload.get("notify_characteristic", fallback.notify_characteristic),
        )

    def to_profile(self) -> BleDeviceProfile:
        return BleDeviceProfile(
            address=self.address,
            service_uuid=self.service_uuid,
            write_characteristic=self.write_characteristic,
            notify_characteristic=self.notify_characteristic,
        )


@dataclass
class VibrationCommandSettings:
    """描述单个震动命令的载荷。"""

    intensity: int = 0
    duration_steps: int = 0

    @classmethod
    def from_dict(
        cls, payload: Dict[str, Any] | None, fallback: "VibrationCommandSettings"
    ) -> "VibrationCommandSettings":
        payload = payload or {}
        intensity = _clamp(payload.get("intensity", fallback.intensity), lower=0, upper=100)
        if "duration_steps" in payload:
            duration_steps = _clamp(payload["duration_steps"], lower=0, upper=255)
        elif "duration_byte" in payload:
            duration_steps = _clamp(payload["duration_byte"], lower=0, upper=255)
        elif payload.get("continuous") is True:
            duration_steps = 0
        elif "duration_ms" in payload:
            duration_steps = _duration_to_steps(payload["duration_ms"])
        else:
            duration_steps = fallback.duration_steps
        return cls(intensity=intensity, duration_steps=duration_steps)

    def merged(self, overrides: Dict[str, Any]) -> "VibrationCommandSettings":
        return self.from_dict(overrides, self)

    def to_payload(self) -> bytes:
        return bytes([self.intensity, self.duration_steps])

    @property
    def duration_ms(self) -> int:
        if self.duration_steps <= 0:
            return 0
        return int(self.duration_steps * 50)


def _default_device() -> BleConnectionConfig:
    return BleConnectionConfig(
        address="AA:BB:CC:DD:EE:FF",
        service_uuid="8653000a-43e6-47b7-9cb0-5fc21d4ae340",
        write_characteristic="8653000c-43e6-47b7-9cb0-5fc21d4ae340",
        notify_characteristic="8653000b-43e6-47b7-9cb0-5fc21d4ae340",
    )


def _default_start() -> VibrationCommandSettings:
    return VibrationCommandSettings(intensity=80, duration_steps=_duration_to_steps(2000))


def _default_stop() -> VibrationCommandSettings:
    return VibrationCommandSettings(intensity=0, duration_steps=0)


@dataclass
class VibratorConfig:
    """震动器模块的完整配置。"""

    device: BleConnectionConfig = field(default_factory=_default_device)
    start: VibrationCommandSettings = field(default_factory=_default_start)
    stop: VibrationCommandSettings = field(default_factory=_default_stop)
    connect_timeout: float = 10.0
    operation_timeout: float = 5.0
    enable_notifications: bool = True
    disconnect_on_stop: bool = True
    retry: RetryPolicy = field(default_factory=RetryPolicy)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "VibratorConfig":
        defaults = cls()
        device = BleConnectionConfig.from_dict(payload.get("device"), defaults.device)
        start = VibrationCommandSettings.from_dict(payload.get("start"), defaults.start)
        stop = VibrationCommandSettings.from_dict(payload.get("stop"), defaults.stop)
        connect_timeout = float(payload.get("connect_timeout", defaults.connect_timeout))
        operation_timeout = float(payload.get("operation_timeout", defaults.operation_timeout))
        enable_notifications = bool(payload.get("enable_notifications", defaults.enable_notifications))
        disconnect_on_stop = bool(payload.get("disconnect_on_stop", defaults.disconnect_on_stop))
        retry = RetryPolicy.from_dict(payload.get("retry"), defaults.retry)
        return cls(
            device=device,
            start=start,
            stop=stop,
            connect_timeout=connect_timeout,
            operation_timeout=operation_timeout,
            enable_notifications=enable_notifications,
            disconnect_on_stop=disconnect_on_stop,
            retry=retry,
        )

    @classmethod
    def from_file(cls, file_path: Path) -> "VibratorConfig":
        file_path = file_path.resolve()
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            LOG.warning("未找到震动器配置文件 %s，使用默认配置", file_path)
            return cls()
        except json.JSONDecodeError as exc:
            LOG.error("震动器配置解析失败: %s", exc)
            return cls()
        return cls.from_dict(data)

    def merged(self, overrides: Dict[str, Any]) -> "VibratorConfig":
        if not overrides:
            return self
        config = replace(self)
        if "device" in overrides:
            config.device = BleConnectionConfig.from_dict(overrides["device"], config.device)
        if "start" in overrides:
            config.start = config.start.merged(overrides["start"])
        if "stop" in overrides:
            config.stop = config.stop.merged(overrides["stop"])
        if "connect_timeout" in overrides:
            config.connect_timeout = float(overrides["connect_timeout"])
        if "operation_timeout" in overrides:
            config.operation_timeout = float(overrides["operation_timeout"])
        if "enable_notifications" in overrides:
            config.enable_notifications = bool(overrides["enable_notifications"])
        if "disconnect_on_stop" in overrides:
            config.disconnect_on_stop = bool(overrides["disconnect_on_stop"])
        if "retry" in overrides:
            config.retry = RetryPolicy.from_dict(overrides["retry"], config.retry)
        return config