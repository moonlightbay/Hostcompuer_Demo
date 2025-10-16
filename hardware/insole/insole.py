"""鞋垫硬件模块的总线适配层，负责指令响应与线程调度。"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from bus.event_bus import EventBus, Subscription
from bus.topics import Topics, register_module_topics
from hardware.iHardware import IHardware
from utils.communication.udp import UdpReceiver, UdpSender

from .config import InsoleConfig
from .core.processor import InsoleProcessor, ProcessedFrame
from .io.logger import DataLogger

InsoleTopics = Topics.Hardware.Insole

LOG = logging.getLogger(__name__)


class InsoleModule(IHardware):
    """实现 IHardware 接口的鞋垫模块，实现启动、停止与数据广播。"""

    topics = {
        "publish": [InsoleTopics.STATUS, InsoleTopics.DATA],
        "subscribe": [InsoleTopics.COMMAND],
    }

    def __init__(self, bus: EventBus, config: InsoleConfig, *, config_root: Path | None = None) -> None:
        """初始化模块，保存配置并准备数据处理、UDP 管理器等成员。"""

        super().__init__(name="insole", bus=bus)
        self.config = config
        self._config_root = config_root or Path.cwd()
        self._lock = threading.RLock()
        self._subscriptions: list[Subscription] = []
        self._receivers: list[UdpReceiver] = []
        self._senders: list[UdpSender] = []
        self._connection_timer: Optional[threading.Timer] = None
        self._auto_stop_timer: Optional[threading.Timer] = None
        self._processor = InsoleProcessor(
            left_csv=config.left_csv,
            right_csv=config.right_csv,
            ad_threshold=config.ad_threshold,
            left_port=config.left.listen_port,
            right_port=config.right.listen_port,
        )
        self._logger: Optional[DataLogger] = None
        self._running = False
        self._frame_counter = 0
        self._active_config: Optional[InsoleConfig] = None

    def attach(self) -> None:
        """在应用启动阶段调用，注册指令监听并广播就绪状态。"""
        LOG.debug("Attaching insole module to bus")
        sub = self.bus.subscribe(InsoleTopics.COMMAND, self._on_bus_command)
        self._subscriptions.append(sub)
        self.publish(InsoleTopics.STATUS, event="ready", payload=None)

    def detach(self) -> None:
        """注销指令监听并释放网络资源。"""
        LOG.debug("Detaching insole module from bus")
        self.stop()
        for sub in self._subscriptions:
            sub.unsubscribe()
        self._subscriptions.clear()

    def handle_command(self, action: str, payload: Dict[str, Any] | None = None) -> None:
        """处理来自总线的控制指令，例如 start、stop 等。"""
        payload = payload or {}
        if action == "start":
            self.start(payload)
        elif action == "stop":
            self.stop()
        elif action == "reload_calibration":
            self.reload_calibration(payload)
        else:
            LOG.warning("Unknown insole command: %s", action)

    def shutdown(self) -> None:
        """模块退出钩子，供主程序在关闭时调用。"""
        self.detach()

    def start(self, overrides: Dict[str, Any] | None = None) -> None:
        """启动硬件，会读取配置、打开 UDP、发送 start 指令。"""
        overrides = overrides or {}
        with self._lock:
            if self._running:
                LOG.info("Insole module already running; ignoring start command")
                return
        effective_config = self.config.merged(overrides, base_dir=self._config_root)
        LOG.info(
            "Starting insole module: bind_ip=%s left_port=%s right_port=%s",
            effective_config.bind_ip,
            effective_config.left.listen_port,
            effective_config.right.listen_port,
        )
        self._processor.ad_threshold = int(effective_config.ad_threshold)
        self._processor.set_ports(effective_config.left.listen_port, effective_config.right.listen_port)
        self._processor.reload_calibration(
            left_csv=effective_config.left_csv,
            right_csv=effective_config.right_csv,
        )
        self._report_calibration_usage(effective_config)
        self._build_receivers(effective_config)
        self._build_senders(effective_config)
        logger = DataLogger(out_dir=effective_config.record_dir)
        logger.start_session(meta=self._session_meta(effective_config))
        with self._lock:
            self._logger = logger
            self._running = True
            self.connected = False
            self._frame_counter = 0
            self._active_config = effective_config
            self._schedule_connection_check(effective_config.connect_timeout)
            self._schedule_auto_stop(effective_config.auto_stop_seconds)
        self.publish(InsoleTopics.STATUS, event="starting", payload=self._session_meta(effective_config))
        self._send_command("start")

    def stop(self) -> None:
        """停止硬件采集，关闭 UDP 并结束日志写入。"""
        with self._lock:
            if not self._running:
                return
            self._running = False
        LOG.info("Stopping insole module")
        self._cancel_timer("_connection_timer")
        self._cancel_timer("_auto_stop_timer")
        self._send_command("stop")
        for receiver in self._receivers:
            receiver.stop()
        self._receivers.clear()
        for sender in self._senders:
            sender.close()
        self._senders.clear()
        logger = self._logger
        if logger:
            try:
                saved_path = logger.stop_session(save=True)
                if saved_path:
                    LOG.info("Session saved to %s", saved_path)
            finally:
                self._logger = None
        with self._lock:
            self._active_config = None
        self.connected = False
        self.publish(InsoleTopics.STATUS, event="stopped", payload=None)

    def reload_calibration(self, payload: Dict[str, Any]) -> None:
        """重新加载校准文件，可在运行时动态更新参数。"""
        with self._lock:
            config = self._active_config or self.config
        new_config = config.merged(payload, base_dir=self._config_root)
        LOG.info("Reloading calibration for insole module")
        self._processor.reload_calibration(
            left_csv=new_config.left_csv,
            right_csv=new_config.right_csv,
        )
        with self._lock:
            self.config = new_config
            if self._running:
                self._active_config = new_config

    def _on_bus_command(
        self,
        action: str,
        payload: Dict[str, Any] | None = None,
        overrides: Dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        """统一整理指令载荷，兼容 payload/overrides 两种字段。"""
        merged: Dict[str, Any] = {}
        if payload:
            merged.update(payload)
        if overrides:
            merged.update(overrides)
        self.handle_command(action, merged)

    def _build_receivers(self, config: InsoleConfig) -> None:
        """基于配置创建并启动左右脚的 UDP 监听器。"""
        for receiver in self._receivers:
            receiver.stop()
        self._receivers.clear()
        left = UdpReceiver(config.left.listen_port, self._on_udp_frame, config.bind_ip)
        right = UdpReceiver(config.right.listen_port, self._on_udp_frame, config.bind_ip)
        try:
            left.start()
            right.start()
        except Exception as exc:
            LOG.exception("Failed to start UDP receivers: %s", exc)
            left.stop()
            right.stop()
            self.publish(InsoleTopics.STATUS, event="receiver_error", payload={"message": str(exc)})
            raise
        self._receivers.extend([left, right])

    def _build_senders(self, config: InsoleConfig) -> None:
        """创建用于发送 start/stop 指令的 UDP 发送器。"""
        for sender in self._senders:
            sender.close()
        self._senders.clear()
        left = UdpSender(config.left.remote_ip, config.left.remote_port)
        right = UdpSender(config.right.remote_ip, config.right.remote_port)
        self._senders.extend([left, right])

    def _send_command(self, command: str) -> None:
        """向左右脚设备广播控制指令。"""
        if not self._senders:
            LOG.warning("No UDP senders available for command '%s'", command)
            return
        for sender in self._senders:
            sender.send(command)

    def _schedule_connection_check(self, timeout: float) -> None:
        """设置连接超时定时器，超时未收到数据将发出警告。"""
        self._cancel_timer("_connection_timer")
        if timeout and timeout > 0:
            self._connection_timer = threading.Timer(timeout, self._connection_timeout)
            self._connection_timer.daemon = True
            self._connection_timer.start()

    def _schedule_auto_stop(self, timeout: Optional[float]) -> None:
        """可选的自动停止定时器，方便测试模式自动收尾。"""
        self._cancel_timer("_auto_stop_timer")
        if timeout and timeout > 0:
            self._auto_stop_timer = threading.Timer(timeout, self.stop)
            self._auto_stop_timer.daemon = True
            self._auto_stop_timer.start()

    def _cancel_timer(self, attr: str) -> None:
        """取消并清理指定名称的定时器对象。"""
        timer = getattr(self, attr, None)
        if timer:
            timer.cancel()
        setattr(self, attr, None)

    def _connection_timeout(self) -> None:
        """在限定时间内未收到硬件数据时触发告警事件。"""
        with self._lock:
            if self.connected or not self._running:
                return
        LOG.warning("Insole hardware did not respond within timeout")
        self.publish(InsoleTopics.STATUS, event="connection_timeout", payload=None)

    def _on_udp_frame(self, frame: str, port: int) -> None:
        """UDP 回调：处理数据帧并广播解析结果。"""
        with self._lock:
            if not self._running:
                return
            logger = self._logger
        result = self._processor.process(frame, port)
        if result is None:
            return
        with self._lock:
            if not self.connected:
                self.connected = True
                self.publish(InsoleTopics.STATUS, event="connected", payload={"port": port})
                self._cancel_timer("_connection_timer")
            frame_index = self._frame_counter
            self._frame_counter += 1
        if logger and logger.active:
            logger.append(result.is_left, result.pressure_matrix, ts=result.timestamp)
        payload = self._frame_payload(result, frame_index)
        self.publish(InsoleTopics.DATA, frame=payload)

    def _session_meta(self, config: InsoleConfig) -> Dict[str, Any]:
        """构建会话元信息，便于记录与 UI 展示配置详情。"""
        return {
            "bind_ip": config.bind_ip,
            "ad_threshold": config.ad_threshold,
            "connect_timeout": config.connect_timeout,
            "auto_stop_seconds": config.auto_stop_seconds,
            "left": {
                "listen_port": config.left.listen_port,
                "remote_port": config.left.remote_port,
                "remote_ip": config.left.remote_ip,
            },
            "right": {
                "listen_port": config.right.listen_port,
                "remote_port": config.right.remote_port,
                "remote_ip": config.right.remote_ip,
            },
            "left_csv": str(config.left_csv) if config.left_csv else None,
            "right_csv": str(config.right_csv) if config.right_csv else None,
            "record_dir": str(config.record_dir),
            "calibration_points": {
                "left": len(self._processor.left_params),
                "right": len(self._processor.right_params),
            },
        }

    def _frame_payload(self, result: ProcessedFrame, frame_index: int) -> Dict[str, Any]:
        """将处理结果组织成标准化结构，供总线广播使用。"""
        return {
            "frame_index": frame_index,
            "timestamp": result.timestamp,
            "side": "left" if result.is_left else "right",
            "port": result.port,
            "stats": result.stats,
            "pressure": result.pressure_matrix.tolist(),
        }

    def _report_calibration_usage(self, config: InsoleConfig) -> None:
        """校准文件加载后输出统计，便于排查配置路径问题。"""

        left_count = len(self._processor.left_params)
        right_count = len(self._processor.right_params)
        if config.left_csv and left_count == 0:
            LOG.warning("左脚校准文件 %s 未加载到有效数据", config.left_csv)
        if config.right_csv and right_count == 0:
            LOG.warning("右脚校准文件 %s 未加载到有效数据", config.right_csv)


register_module_topics(
    "insole",
    publish={
        InsoleTopics.STATUS: "鞋垫模块生命周期与连接状态事件",
        InsoleTopics.DATA: "鞋垫硬件解析后的压力帧数据",
    },
    subscribe={
        InsoleTopics.COMMAND: "控制鞋垫硬件的指令（start/stop 等）",
    },
)