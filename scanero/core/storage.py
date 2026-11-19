"""Persistent settings, favorites and scan history."""
from __future__ import annotations

import ipaddress
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import Device, Favorite


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    path = Path(base) / "scanero"
    old = Path(base) / "netscope"
    if old.exists() and not path.exists():
        try:
            shutil.copytree(old, path)
        except Exception:
            pass
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except Exception:
            pass


DEFAULT_SETTINGS: dict[str, Any] = {
    "range": "",
    "interface": "",
    "threads": 96,
    "speed": 3,
    "ping_timeout": 1.0,
    "port_timeout": 0.35,
    "scan_services": True,
    "resolve_names": True,
    "use_netbios": True,
    "use_mdns": True,
    "use_ssdp": True,
    "use_snmp": True,
    "tcp_discovery": True,
    "ports": "21,22,23,53,80,135,139,443,445,515,554,631,3389,5000,5900,8080,8443,9100",
    "notify": True,
    "theme": "system",
    "font_scale": 1.0,
    "filter": "online",
    "window_size": [1400, 900],
    "window_pos": [],
    "export_dir": "",
    "last_page": "scanner",
}

SPEED_MAP = {
    1: {"threads": 24, "ping_timeout": 1.6, "port_timeout": 0.6},
    2: {"threads": 48, "ping_timeout": 1.3, "port_timeout": 0.5},
    3: {"threads": 96, "ping_timeout": 1.0, "port_timeout": 0.35},
    4: {"threads": 160, "ping_timeout": 0.8, "port_timeout": 0.28},
    5: {"threads": 256, "ping_timeout": 0.6, "port_timeout": 0.2},
}


class Settings:
    def __init__(self) -> None:
        self.path = config_dir() / "settings.json"
        self.data = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                saved = json.load(fh)
            if isinstance(saved, dict):
                for key, value in saved.items():
                    if key in DEFAULT_SETTINGS:
                        self.data[key] = value
        except Exception:
            pass

    def save(self) -> None:
        try:
            _atomic_write(self.path, json.dumps(self.data, ensure_ascii=False, indent=2))
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, DEFAULT_SETTINGS.get(key, default))

    def set(self, key: str, value: Any, *, save: bool = True) -> None:
        self.data[key] = value
        if save:
            self.save()

    def update(self, values: dict[str, Any], *, save: bool = True) -> None:
        self.data.update(values)
        if save:
            self.save()

    @property
    def ports(self) -> list[int]:
        raw = str(self.get("ports", ""))
        result: list[int] = []
        for token in raw.replace(";", ",").replace(" ", ",").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                port = int(token)
            except ValueError:
                continue
            if 1 <= port <= 65535 and port not in result:
                result.append(port)
        return result or [80]


class FavoritesStore:
    def __init__(self) -> None:
        self.path = config_dir() / "favorites.json"
        self.items: list[Favorite] = []
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            items = data.get("favorites", data) if isinstance(data, dict) else data
            self.items = [Favorite.from_dict(item) for item in items if isinstance(item, dict)]
        except Exception:
            self.items = []

    def save(self) -> None:
        try:
            payload = {"version": 1, "favorites": [f.to_dict() for f in self.items]}
            _atomic_write(self.path, json.dumps(payload, ensure_ascii=False, indent=2))
        except Exception:
            pass

    def __len__(self) -> int:
        return len(self.items)

    def find(self, device: Device | None = None, *, ip: str = "", mac: str = "") -> Favorite | None:
        for fav in self.items:
            if fav.matches(device, ip=ip, mac=mac):
                return fav
        return None

    def contains(self, device: Device | None = None, *, ip: str = "", mac: str = "") -> bool:
        return self.find(device, ip=ip, mac=mac) is not None

    def add(self, device: Device | None = None, *, ip: str = "", mac: str = "",
            name: str = "", vendor: str = "", note: str = "") -> Favorite:
        if device is not None:
            ip, mac, name, vendor = device.ip, device.mac, device.name, device.vendor
        existing = self.find(ip=ip, mac=mac)
        if existing:
            existing.ip = ip or existing.ip
            existing.mac = mac or existing.mac
            existing.name = name or existing.name
            existing.vendor = vendor or existing.vendor
            if device is not None:
                existing.kind = device.kind
                existing.os_name = device.os_name
            if note:
                existing.note = note
            existing.last_seen = time.time()
            self.save()
            return existing
        fav = Favorite(
            ip=ip,
            mac=mac,
            name=name,
            vendor=vendor,
            note=note,
            kind=device.kind if device is not None else "unknown",
            os_name=device.os_name if device is not None else "",
            added=time.time(),
            last_seen=time.time(),
        )
        self.items.append(fav)
        self.save()
        return fav

    def remove(self, favorite: Favorite | Device | None = None, *, ip: str = "", mac: str = "") -> bool:
        if isinstance(favorite, Device):
            target = self.find(favorite)
        elif isinstance(favorite, Favorite):
            target = favorite
        else:
            target = self.find(ip=ip, mac=mac)
        if target in self.items:
            self.items.remove(target)
            self.save()
            return True
        return False

    def update_from_device(self, device: Device) -> None:
        fav = self.find(device)
        if not fav:
            return
        fav.ip = device.ip or fav.ip
        fav.mac = device.mac or fav.mac
        fav.name = device.name or fav.name
        fav.vendor = device.vendor or fav.vendor
        fav.kind = device.kind or fav.kind
        fav.os_name = device.os_name or fav.os_name
        fav.last_seen = time.time()
        self.save()

    def import_data(self, payload: Any) -> int:
        items = payload.get("favorites", payload) if isinstance(payload, dict) else payload
        imported = 0
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            fav = Favorite.from_dict(item)
            try:
                ipaddress.IPv4Address(fav.ip)
            except Exception:
                continue
            if self.find(ip=fav.ip, mac=fav.mac):
                continue
            self.items.append(fav)
            imported += 1
        if imported:
            self.save()
        return imported


@dataclass
class HistoryEntry:
    id: str
    timestamp: float
    range_expr: str
    target_count: int
    online: int
    offline: int
    services: int
    duration: float
    devices: list[dict] = field(default_factory=list)

    @property
    def date_label(self) -> str:
        return time.strftime("%d.%m.%Y · %H:%M", time.localtime(self.timestamp))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "range": self.range_expr,
            "target_count": self.target_count,
            "online": self.online,
            "offline": self.offline,
            "services": self.services,
            "duration": self.duration,
            "devices": self.devices,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryEntry":
        return cls(
            id=str(data.get("id", "")),
            timestamp=float(data.get("timestamp", 0) or 0),
            range_expr=data.get("range", ""),
            target_count=int(data.get("target_count", 0) or 0),
            online=int(data.get("online", 0) or 0),
            offline=int(data.get("offline", 0) or 0),
            services=int(data.get("services", 0) or 0),
            duration=float(data.get("duration", 0) or 0),
            devices=list(data.get("devices", [])),
        )

    def device_objects(self) -> list[Device]:
        return [Device.from_dict(item) for item in self.devices if isinstance(item, dict)]


class HistoryStore:
    def __init__(self, limit: int = 20) -> None:
        self.path = config_dir() / "history.json"
        self.limit = limit
        self.items: list[HistoryEntry] = []
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            entries = data.get("history", data) if isinstance(data, dict) else data
            self.items = [HistoryEntry.from_dict(item) for item in entries if isinstance(item, dict)]
        except Exception:
            self.items = []

    def save(self) -> None:
        try:
            payload = {"version": 1, "history": [e.to_dict() for e in self.items[: self.limit]]}
            _atomic_write(self.path, json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    def add(self, entry: HistoryEntry) -> None:
        self.items.insert(0, entry)
        self.items = self.items[: self.limit]
        self.save()

    def clear(self) -> None:
        self.items = []
        self.save()
