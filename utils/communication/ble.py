"""Bluetooth Low Energy communication utilities built on bleak."""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional, TypeVar

try:  # pragma: no cover - Import guard for optional dependency
    from bleak import BleakClient as _BleakClient  # type: ignore[import]
except ImportError as exc:  # pragma: no cover - 提示用户安装依赖
    _BLE_IMPORT_ERROR = exc
    _BleakClient = None  # type: ignore[assignment]
else:
    _BLE_IMPORT_ERROR = None

BleakClientType = Any

LOG = logging.getLogger(__name__)


class BleCommunicationError(RuntimeError):
    """统一封装蓝牙通信异常。"""


NotificationHandler = Callable[[bytes], None]


@dataclass
class BleDeviceProfile:
    """描述 BLE 设备地址与特征值。"""

    address: str
    service_uuid: str
    write_characteristic: str
    notify_characteristic: Optional[str] = None


_T = TypeVar("_T")


class BleDeviceClient:
    """基于 bleak 的同步封装，隐藏 asyncio 与线程细节。"""

    def __init__(
        self,
        profile: BleDeviceProfile,
        *,
        connect_timeout: float = 10.0,
        operation_timeout: float = 5.0,
    ) -> None:
        self.profile = profile
        self.connect_timeout = connect_timeout
        self.operation_timeout = operation_timeout
        if _BleakClient is None:
            raise ImportError("缺少 bleak 库，请执行 `pip install bleak` 安装蓝牙依赖。") from _BLE_IMPORT_ERROR
        self._BleakClient = _BleakClient
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="BleDeviceClient.loop", daemon=True)
        self._thread.start()
        self._client: Optional[BleakClientType] = None
        self._notification_handler: Optional[NotificationHandler] = None
        self._notify_active = False
        self._callback_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="BleNotify")
        self._shutdown = False

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _submit(self, coro: Coroutine[None, None, _T], *, timeout: Optional[float] = None) -> _T:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        limit = timeout if timeout is not None else self.operation_timeout
        try:
            return future.result(limit)
        except asyncio.TimeoutError as exc:
            future.cancel()
            raise BleCommunicationError("蓝牙操作超时") from exc
        except Exception as exc:
            raise BleCommunicationError(str(exc)) from exc

    def connect(self) -> None:
        """建立 BLE 连接。"""

        self._submit(self._connect_async(), timeout=self.connect_timeout)

    def disconnect(self) -> None:
        """断开 BLE 连接。"""

        self._submit(self._disconnect_async())

    def close(self) -> None:
        """关闭客户端并释放后台线程。"""

        if self._shutdown:
            return
        self._shutdown = True
        try:
            self._submit(self._disconnect_async())
        except BleCommunicationError:
            LOG.debug("关闭 BLE 客户端时忽略断开异常", exc_info=True)
        self._callback_executor.shutdown(wait=False)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=1.0)

    def write(self, payload: bytes, *, response: bool = True) -> None:
        """向写特征值发送数据。"""

        self._submit(self._write_async(payload, response=response))

    def set_notification_handler(self, handler: Optional[NotificationHandler]) -> None:
        """注册或清除通知回调。"""

        self._notification_handler = handler
        if handler is None:
            self._submit(self._disable_notify_async())
        elif self._client and getattr(self._client, "is_connected", False):
            self._submit(self._start_notify_async())

    async def _connect_async(self) -> None:
        if self._client and getattr(self._client, "is_connected", False):
            return
        if self._client:
            await self._client.disconnect()
        client = self._BleakClient(self.profile.address, timeout=self.connect_timeout)
        try:
            await asyncio.wait_for(client.connect(), timeout=self.connect_timeout)
        except Exception:
            await client.disconnect()
            raise
        self._client = client
        if self._notification_handler is not None and self.profile.notify_characteristic:
            await self._start_notify_async()

    async def _disconnect_async(self) -> None:
        if self._client is None:
            return
        try:
            if self._notify_active and self.profile.notify_characteristic:
                await self._client.stop_notify(self.profile.notify_characteristic)
        finally:
            try:
                await self._client.disconnect()
            finally:
                self._client = None
                self._notify_active = False

    async def _write_async(self, payload: bytes, *, response: bool) -> None:
        await self._connect_async()
        if not self._client:
            raise BleCommunicationError("BLE 客户端未初始化")
        await self._client.write_gatt_char(self.profile.write_characteristic, payload, response=response)

    async def _disable_notify_async(self) -> None:
        if not self._client or not self._notify_active or not self.profile.notify_characteristic:
            return
        await self._client.stop_notify(self.profile.notify_characteristic)
        self._notify_active = False

    async def _start_notify_async(self) -> None:
        if not self._client or not self.profile.notify_characteristic or self._notify_active:
            return

        def _callback(_: int, data: bytearray) -> None:
            handler = self._notification_handler
            if handler is None:
                return
            payload = bytes(data)
            self._callback_executor.submit(handler, payload)

        await self._client.start_notify(self.profile.notify_characteristic, _callback)
        self._notify_active = True

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        try:
            self.close()
        except Exception:
            LOG.debug("忽略 BLE 客户端析构异常", exc_info=True)


__all__ = [
	"BleCommunicationError",
	"BleDeviceClient",
	"BleDeviceProfile",
]
