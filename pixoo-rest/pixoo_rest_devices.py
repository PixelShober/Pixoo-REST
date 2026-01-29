"""Device registry for Pixoo REST multi-device support."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable

from pixoo import Pixoo

from pixoo_rest.core.config import settings


@dataclass
class DeviceContext:
    key: str
    host: str
    device_type: str
    screen_size: int
    debug: bool
    connection_retries: int
    pixoo: Pixoo | None = None
    name: str | None = None


class DeviceRegistry:
    def __init__(self, devices: Iterable[DeviceContext]):
        self.devices = list(devices)
        self._by_key = {device.key.lower(): device for device in self.devices}
        self._by_host = {device.host: device for device in self.devices}
        self.default = self.devices[0] if self.devices else None

    def select(self, device_key: str | None, host: str | None) -> DeviceContext | None:
        if device_key:
            return self._by_key.get(device_key.lower())
        if host:
            return self._by_host.get(host)
        return self.default

    def keys(self) -> list[str]:
        return [device.key for device in self.devices]

    def hosts(self) -> list[str]:
        return [device.host for device in self.devices]


DEVICE_REGISTRY: DeviceRegistry | None = None


def initialize_device_registry(devices: Iterable[DeviceContext]) -> DeviceRegistry:
    global DEVICE_REGISTRY
    DEVICE_REGISTRY = DeviceRegistry(devices)
    return DEVICE_REGISTRY


def get_device_registry() -> DeviceRegistry:
    if DEVICE_REGISTRY is None:
        raise RuntimeError("Device registry is not initialized")
    return DEVICE_REGISTRY


def normalize_device_type(value: str | None) -> str:
    normalized = (value or "pixoo").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    if normalized in ("timegate", "time_gate"):
        return "time_gate"
    if normalized == "auto":
        return "auto"
    return "pixoo"


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(value)


def _ensure_unique_key(key: str, existing: set[str]) -> str:
    if key not in existing:
        existing.add(key)
        return key
    suffix = 2
    while f"{key}-{suffix}" in existing:
        suffix += 1
    unique = f"{key}-{suffix}"
    existing.add(unique)
    return unique


def _load_devices_from_list(raw_devices: list[object]) -> list[DeviceContext]:
    devices: list[DeviceContext] = []
    used_keys: set[str] = set()

    for raw in raw_devices:
        if not isinstance(raw, dict):
            continue
        host = str(raw.get("host") or "").strip()
        if not host:
            continue
        name = str(raw.get("name") or "").strip() or None
        key = str(raw.get("key") or name or host).strip()
        if not key:
            key = host
        key = _ensure_unique_key(key, used_keys)

        device_type = normalize_device_type(raw.get("device_type"))
        screen_size = _coerce_int(raw.get("screen_size"), settings.pixoo_screen_size)
        debug = _coerce_bool(raw.get("debug"), settings.pixoo_debug)
        retries = _coerce_int(
            raw.get("connection_retries"),
            settings.pixoo_test_connection_retries,
        )

        devices.append(
            DeviceContext(
                key=key,
                host=host,
                device_type=device_type,
                screen_size=screen_size,
                debug=debug,
                connection_retries=retries,
                name=name,
            )
        )

    return devices


def load_devices_from_env() -> list[DeviceContext]:
    devices_json = os.getenv("PIXOO_DEVICES_JSON", "").strip()
    if devices_json:
        try:
            raw_devices = json.loads(devices_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("PIXOO_DEVICES_JSON is not valid JSON") from exc
        if not isinstance(raw_devices, list):
            raise RuntimeError("PIXOO_DEVICES_JSON must be a JSON array")
        devices = _load_devices_from_list(raw_devices)
        if devices:
            return devices

    device_type = normalize_device_type(os.getenv("PIXOO_DEVICE_TYPE"))
    return [
        DeviceContext(
            key=settings.pixoo_host,
            host=settings.pixoo_host,
            device_type=device_type,
            screen_size=settings.pixoo_screen_size,
            debug=settings.pixoo_debug,
            connection_retries=settings.pixoo_test_connection_retries,
        )
    ]
