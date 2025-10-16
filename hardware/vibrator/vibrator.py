"""震动器硬件模块，封装 BLE 指令发送逻辑。"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

from bus.event_bus import EventBus, Subscription
from bus.topics import Topics, register_module_topics
from hardware.iHardware import IHardware
from utils.communication.ble import BleCommunicationError, BleDeviceClient

from .config import VibratorConfig, VibrationCommandSettings
from .core import COMMAND_OFF, COMMAND_ON, build_packet

LOG = logging.getLogger(__name__)

VibratorTopics = Topics.Hardware.Vibrator


class VibratorModule(IHardware):
    """实现 IHardware 接口的震动器模块。"""

    topics = {
        "publish": [VibratorTopics.STATUS, VibratorTopics.NOTIFY],
        "subscribe": [VibratorTopics.COMMAND],
    }

    def __init__(self, bus: EventBus, config: VibratorConfig) -> None:
        super().__init__(name="vibrator", bus=bus)
        self.config = config
        self._lock = threading.RLock()
        self._subscriptions: list[Subscription] = []
        self._client = BleDeviceClient(
            config.device.to_profile(),
            connect_timeout=config.connect_timeout,
            operation_timeout=config.operation_timeout,
        )
        self._retry = config.retry
        if config.enable_notifications and config.device.notify_characteristic:
            self._client.set_notification_handler(self._on_notification)
        self._running = False

    def attach(self) -> None:
        LOG.debug("Attaching vibrator module")
        sub = self.bus.subscribe(VibratorTopics.COMMAND, self._on_bus_command)
        self._subscriptions.append(sub)
        self.publish(VibratorTopics.STATUS, event="ready", payload=None)

    def detach(self) -> None:
        LOG.debug("Detaching vibrator module")
        self.stop()
        for sub in self._subscriptions:
            sub.unsubscribe()
        self._subscriptions.clear()
        self._client.close()

    def handle_command(self, action: str, payload: Dict[str, Any] | None = None) -> None:
        payload = payload or {}
        normalized = action.lower()
        if normalized in {"start", "开始"}:
            self._start(payload)
        elif normalized in {"stop", "结束"}:
            self._stop(payload)
        elif normalized in {"reload_config", "reload"}:
            self._reload(payload)
        else:
            LOG.warning("Unknown vibrator command: %s", action)

    def shutdown(self) -> None:
        self.detach()

    def stop(self) -> None:
        self._stop({})

    def _start(self, overrides: Dict[str, Any]) -> None:
        settings = self.config.start.merged(overrides.get("settings", overrides))
        if self._send_command(COMMAND_ON, settings, "start"):
            self.publish(
                VibratorTopics.STATUS,
                event="running",
                payload={"intensity": settings.intensity, "duration_steps": settings.duration_steps},
            )
            with self._lock:
                self._running = True

    def _stop(self, overrides: Dict[str, Any]) -> None:
        settings = self.config.stop.merged(overrides.get("settings", overrides))
        if self._send_command(COMMAND_OFF, settings, "stop"):
            self.publish(VibratorTopics.STATUS, event="stopped", payload=None)
            with self._lock:
                self._running = False
            if self.config.disconnect_on_stop:
                try:
                    self._client.disconnect()
                except BleCommunicationError as exc:  # pragma: no cover - 清理阶段异常不影响主流程
                    LOG.debug("忽略断开异常: %s", exc)
                self.connected = False

    def _reload(self, overrides: Dict[str, Any]) -> None:
        previous = self.config
        new_config = self.config.merged(overrides)
        replace_client = (
            new_config.device != previous.device
            or new_config.connect_timeout != previous.connect_timeout
            or new_config.operation_timeout != previous.operation_timeout
        )
        if replace_client:
            try:
                self._client.close()
            except Exception:  # pragma: no cover - best effort cleanup
                LOG.debug("关闭旧蓝牙客户端时出现异常", exc_info=True)
            self._client = BleDeviceClient(
                new_config.device.to_profile(),
                connect_timeout=new_config.connect_timeout,
                operation_timeout=new_config.operation_timeout,
            )
            self.connected = False
        self.config = new_config
        self._retry = new_config.retry
        if new_config.enable_notifications and new_config.device.notify_characteristic:
            self._client.set_notification_handler(self._on_notification)
        else:
            self._client.set_notification_handler(None)
        self.publish(VibratorTopics.STATUS, event="config_reloaded", payload=overrides)

    def _send_command(self, command: int, settings: VibrationCommandSettings, action: str) -> bool:
        packet = build_packet(command, settings.intensity, settings.duration_steps)
        attempts = max(1, self._retry.attempts)
        for attempt in range(1, attempts + 1):
            try:
                self._client.write(packet)
                with self._lock:
                    if not self.connected:
                        self.connected = True
                        self.publish(VibratorTopics.STATUS, event="connected", payload=None)
                self.publish(
                    VibratorTopics.STATUS,
                    event="command_sent",
                    payload={
                        "action": action,
                        "intensity": settings.intensity,
                        "duration_steps": settings.duration_steps,
                    },
                )
                return True
            except BleCommunicationError as exc:
                LOG.warning("发送震动指令失败(%s/%s): %s", attempt, attempts, exc)
                self.publish(
                    VibratorTopics.STATUS,
                    event="error",
                    payload={"action": action, "message": str(exc), "attempt": attempt},
                )
                if attempt < attempts:
                    time.sleep(self._retry.interval_seconds)
                else:
                    return False
        return False

    def _on_notification(self, payload: bytes) -> None:
        self.publish(
            VibratorTopics.NOTIFY,
            event="notification",
            payload={"hex": payload.hex(), "bytes": list(payload)},
        )

    def _on_bus_command(self, action: str, payload: Optional[Dict[str, Any]] = None, **_: Any) -> None:
        self.handle_command(action, payload)


register_module_topics(
    "vibrator",
    publish={
        VibratorTopics.STATUS: "震动器状态事件",
        VibratorTopics.NOTIFY: "震动器硬件通知原始数据",
    },
    subscribe={
        VibratorTopics.COMMAND: "震动器控制指令",
    },
)
