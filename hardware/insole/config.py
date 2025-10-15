"""鞋垫模块的配置加载与合并工具。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Optional

from .constants import (
    DEFAULT_BIND_IP,
    DEFAULT_CONNECT_TIMEOUT,
    LEFT_IP,
    LEFT_PORT,
    LEFT_REMOTE_PORT,
    MIN_VALID_AD,
    RIGHT_IP,
    RIGHT_PORT,
    RIGHT_REMOTE_PORT,
)


LOG = logging.getLogger(__name__)


@dataclass
class EndpointConfig:
    """描述单侧鞋垫的网络端口与 IP 配置。"""

    listen_port: int
    remote_port: int
    remote_ip: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any], fallback: "EndpointConfig") -> "EndpointConfig":
        """从字典中解析端口配置，缺失字段回落到 fallback。"""
        return cls(
            listen_port=int(payload.get("listen_port", fallback.listen_port)),
            remote_port=int(payload.get("remote_port", fallback.remote_port)),
            remote_ip=str(payload.get("remote_ip", fallback.remote_ip)),
        )


@dataclass
class InsoleConfig:
    """鞋垫模块的总配置，包含左右脚、超时与数据路径信息。"""

    bind_ip: str = DEFAULT_BIND_IP
    left: EndpointConfig = EndpointConfig(LEFT_PORT, LEFT_REMOTE_PORT, LEFT_IP)
    right: EndpointConfig = EndpointConfig(RIGHT_PORT, RIGHT_REMOTE_PORT, RIGHT_IP)
    left_csv: Optional[Path] = None
    right_csv: Optional[Path] = None
    ad_threshold: int = MIN_VALID_AD
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    auto_stop_seconds: Optional[float] = None
    record_dir: Path = Path("hardware/insole/records")

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, base_dir: Path | None = None) -> "InsoleConfig":
        """从普通字典构造配置对象，支持相对路径自动解析。"""
        base_dir = base_dir or Path.cwd()
        defaults = cls()
        left_cfg = EndpointConfig.from_dict(payload.get("left", {}), defaults.left)
        right_cfg = EndpointConfig.from_dict(payload.get("right", {}), defaults.right)
        record_dir_path = _resolve_search_path(base_dir, payload.get("record_dir", defaults.record_dir))
        left_csv = _resolve_path(base_dir, payload.get("left_csv"))
        right_csv = _resolve_path(base_dir, payload.get("right_csv"))
        return cls(
            bind_ip=str(payload.get("bind_ip", defaults.bind_ip)),
            left=left_cfg,
            right=right_cfg,
            left_csv=left_csv,
            right_csv=right_csv,
            ad_threshold=int(payload.get("ad_threshold", defaults.ad_threshold)),
            connect_timeout=float(payload.get("connect_timeout", defaults.connect_timeout)),
            auto_stop_seconds=_to_optional_float(payload.get("auto_stop_seconds", defaults.auto_stop_seconds)),
            record_dir=record_dir_path,
        )

    @classmethod
    def from_file(cls, file_path: Path) -> "InsoleConfig":
        """读取 JSON 配置文件并解析为 InsoleConfig 对象。"""
        file_path = file_path.resolve()
        data: dict[str, Any]
        with file_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls.from_dict(data, base_dir=file_path.parent)

    def merged(self, overrides: dict[str, Any], *, base_dir: Path | None = None) -> "InsoleConfig":
        """在当前配置基础上应用增量覆盖，返回新的配置对象。"""
        if not overrides:
            return self
        base_dir = base_dir or Path.cwd()
        config = replace(self)
        if "bind_ip" in overrides:
            config.bind_ip = str(overrides["bind_ip"])
        if "ad_threshold" in overrides:
            config.ad_threshold = int(overrides["ad_threshold"])
        if "connect_timeout" in overrides:
            config.connect_timeout = float(overrides["connect_timeout"])
        if "auto_stop_seconds" in overrides:
            config.auto_stop_seconds = _to_optional_float(overrides["auto_stop_seconds"])
        if "record_dir" in overrides:
            record_dir = _resolve_search_path(base_dir, overrides["record_dir"])
            if record_dir is not None:
                config.record_dir = record_dir
        if "left_csv" in overrides:
            config.left_csv = _resolve_path(base_dir, overrides["left_csv"])
        if "right_csv" in overrides:
            config.right_csv = _resolve_path(base_dir, overrides["right_csv"])
        if "left" in overrides:
            config.left = EndpointConfig.from_dict(overrides["left"], config.left)
        if "right" in overrides:
            config.right = EndpointConfig.from_dict(overrides["right"], config.right)
        return config


def _resolve_path(base_dir: Path, value: Any) -> Optional[Path]:
    """根据基准目录与工程根目录查找文件路径，未找到时记录警告。"""

    if value in (None, ""):
        return None
    raw = Path(str(value)).expanduser()
    if raw.is_absolute():
        return raw.resolve()

    candidates = _build_candidate_paths(base_dir, raw)
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.exists():
            return resolved

    LOG.warning("未找到配置文件指定的路径: %s (基准目录: %s)", raw, base_dir)
    return None


def _resolve_search_path(base_dir: Path, value: Any) -> Path:
    """解析目录路径，若不存在则仍返回期望位置以便后续创建。"""

    if value in (None, ""):
        return (base_dir / "").resolve()
    raw = Path(str(value)).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    candidates = _build_candidate_paths(base_dir, raw)
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.exists():
            return resolved
    # 默认返回基准目录拼接，供后续创建
    return (base_dir / raw).resolve()


def _build_candidate_paths(base_dir: Path, relative: Path) -> list[Path]:
    """生成一组可能的相对路径组合，用于兼容项目/配置目录写法。"""

    candidates: list[Path] = []
    search_roots: Iterable[Path] = [base_dir, *base_dir.parents, Path.cwd()]
    parts = relative.parts
    for root in search_roots:
        candidates.append(root / relative)
        if parts and parts[0] == root.name and len(parts) > 1:
            trimmed = Path(*parts[1:])
            candidates.append(root / trimmed)
    return candidates


def _to_optional_float(value: Any) -> Optional[float]:
    """尝试将值转换为浮点数，失败或空值时返回 None。"""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
