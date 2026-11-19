"""Data models shared by the scanner core and the UI."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

# port -> (kind, display name, default scheme)
SERVICE_CATALOG: dict[int, tuple[str, str, str]] = {
    21: ("ftp", "FTP", "ftp"),
    22: ("ssh", "SSH", "ssh"),
    23: ("telnet", "Telnet", "telnet"),
    25: ("smtp", "SMTP", "smtp"),
    53: ("dns", "DNS", ""),
    80: ("http", "HTTP", "http"),
    110: ("pop3", "POP3", "pop3"),
    135: ("rpc", "MS RPC", ""),
    139: ("netbios", "NetBIOS", ""),
    143: ("imap", "IMAP", "imap"),
    443: ("https", "HTTPS", "https"),
    445: ("smb", "SMB", "smb"),
    515: ("lpd", "LPD", ""),
    548: ("afp", "AFP", "afp"),
    587: ("smtp", "SMTP", ""),
    631: ("ipp", "IPP", "ipp"),
    993: ("imap", "IMAPS", ""),
    995: ("pop3", "POP3S", ""),
    3306: ("mysql", "MySQL", ""),
    3389: ("rdp", "RDP", "rdp"),
    5000: ("http", "HTTP-alt", "http"),
    5432: ("postgres", "PostgreSQL", ""),
    5900: ("vnc", "VNC", "vnc"),
    6379: ("redis", "Redis", ""),
    8000: ("http", "HTTP-alt", "http"),
    8080: ("http", "HTTP-alt", "http"),
    8443: ("https", "HTTPS-alt", "https"),
    8888: ("http", "HTTP-alt", "http"),
    9100: ("printer", "RAW печать", ""),
    62078: ("iphone", "iPhone Sync", ""),
    554: ("rtsp", "RTSP", "rtsp"),
    8554: ("rtsp", "RTSP", "rtsp"),
}

# Services that make sense to open in a web browser
WEB_KINDS = {"http", "https"}
TERMINAL_KINDS = {"ssh", "telnet"}
FILE_KINDS = {"smb", "netbios", "ftp", "afp"}


@dataclass
class Service:
    port: int
    kind: str = "tcp"
    name: str = ""
    product: str = ""
    scheme: str = ""
    title: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            meta = SERVICE_CATALOG.get(self.port)
            if meta:
                self.kind, self.name, self.scheme = meta
            else:
                self.name = f"TCP {self.port}"

    @property
    def subtitle(self) -> str:
        parts: list[str] = [f"порт {self.port}"]
        if self.product:
            parts.append(self.product)
        elif self.title:
            parts.append(self.title)
        return " · ".join(parts)

    def url(self, ip: str) -> str:
        if self.kind in ("http", "https"):
            port = "" if self.port in (80, 443) else f":{self.port}"
            return f"{self.kind}://{ip}{port}/"
        if self.kind == "ftp":
            return f"ftp://{ip}/"
        if self.kind in ("smb", "netbios"):
            return f"smb://{ip}/"
        if self.kind == "afp":
            return f"afp://{ip}/"
        if self.kind == "rdp":
            return f"rdp://{ip}"
        if self.kind == "ssh":
            return f"ssh://{ip}"
        if self.kind == "vnc":
            return f"vnc://{ip}"
        if self.kind == "rtsp":
            return f"rtsp://{ip}:{self.port}/"
        if self.kind == "ipp":
            return f"http://{ip}:{self.port}/"
        return f"http://{ip}:{self.port}/"

    def to_dict(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "kind": self.kind,
            "name": self.name,
            "product": self.product,
            "scheme": self.scheme,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Service":
        return cls(
            port=int(data.get("port", 0)),
            kind=data.get("kind", "tcp"),
            name=data.get("name", ""),
            product=data.get("product", ""),
            scheme=data.get("scheme", ""),
            title=data.get("title", ""),
        )


# ---------------------------------------------------------------------------
# Device kinds
# ---------------------------------------------------------------------------

KIND_LABELS: dict[str, str] = {
    "router": "Роутер",
    "computer": "Компьютер",
    "server": "Сервер",
    "printer": "Принтер",
    "phone": "Смартфон",
    "tablet": "Планшет",
    "tv": "Телевизор",
    "camera": "Камера",
    "nas": "NAS",
    "iot": "IoT-устройство",
    "unknown": "Устройство",
}

KIND_ICONS: dict[str, str] = {
    "router": "router",
    "computer": "monitor",
    "server": "server",
    "printer": "printer",
    "phone": "smartphone",
    "tablet": "tablet",
    "tv": "tv",
    "camera": "camera",
    "nas": "hard-drive",
    "iot": "cpu",
    "unknown": "device",
}

KIND_COLORS: dict[str, str] = {
    "router": "#7C8CFF",
    "computer": "#22D3EE",
    "server": "#A78BFA",
    "printer": "#FFC857",
    "phone": "#3DDC97",
    "tablet": "#3DDC97",
    "tv": "#F472B6",
    "camera": "#FB923C",
    "nas": "#38BDF8",
    "iot": "#94A3B8",
    "unknown": "#64748B",
}


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, "Устройство")


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------

STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"
STATUS_UNKNOWN = "unknown"


def ip_to_int(ip: str) -> int:
    try:
        a, b, c, d = (int(part) for part in ip.split("."))
        return (a << 24) | (b << 16) | (c << 8) | d
    except Exception:
        return 0


@dataclass
class Device:
    ip: str
    name: str = ""
    hostname: str = ""
    netbios: str = ""
    workgroup: str = ""
    mac: str = ""
    vendor: str = ""
    status: str = STATUS_UNKNOWN
    ttl: int = 0
    os_name: str = ""
    kind: str = "unknown"
    services: list[Service] = field(default_factory=list)
    last_seen: float = 0.0
    note: str = ""
    via: str = "ping"
    favorite: bool = False

    # -- presentation helpers ------------------------------------------------
    @property
    def title(self) -> str:
        return self.name or self.hostname or self.netbios or ""

    @property
    def status_label(self) -> str:
        return {
            STATUS_ONLINE: "В сети",
            STATUS_OFFLINE: "Не в сети",
            STATUS_UNKNOWN: "Неизвестно",
        }.get(self.status, "Неизвестно")

    @property
    def kind_label(self) -> str:
        return kind_label(self.kind)

    @property
    def service_kinds(self) -> set[str]:
        return {s.kind for s in self.services}

    @property
    def primary_service(self) -> Service | None:
        if not self.services:
            return None
        priority = ["smb", "netbios", "http", "https", "rdp", "ssh", "ftp", "vnc", "ipp", "afp", "rtsp"]
        by_kind = {s.kind: s for s in self.services}
        for kind in priority:
            if kind in by_kind:
                return by_kind[kind]
        return self.services[0]

    @property
    def search_text(self) -> str:
        parts = [
            self.name,
            self.hostname,
            self.netbios,
            self.ip,
            self.mac,
            self.vendor,
            self.os_name,
            self.workgroup,
            self.kind_label,
        ]
        parts.extend(s.name for s in self.services)
        parts.extend(s.product for s in self.services)
        parts.extend(s.title for s in self.services)
        return " ".join(p for p in parts if p).lower()

    def is_online(self) -> bool:
        return self.status == STATUS_ONLINE

    # -- serialization -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "ip": self.ip,
            "name": self.name,
            "hostname": self.hostname,
            "netbios": self.netbios,
            "workgroup": self.workgroup,
            "mac": self.mac,
            "vendor": self.vendor,
            "status": self.status,
            "ttl": self.ttl,
            "os_name": self.os_name,
            "kind": self.kind,
            "services": [s.to_dict() for s in self.services],
            "last_seen": self.last_seen,
            "note": self.note,
            "via": self.via,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Device":
        return cls(
            ip=data.get("ip", ""),
            name=data.get("name", ""),
            hostname=data.get("hostname", ""),
            netbios=data.get("netbios", ""),
            workgroup=data.get("workgroup", ""),
            mac=data.get("mac", ""),
            vendor=data.get("vendor", ""),
            status=data.get("status", STATUS_UNKNOWN),
            ttl=int(data.get("ttl", 0) or 0),
            os_name=data.get("os_name", ""),
            kind=data.get("kind", "unknown"),
            services=[Service.from_dict(s) for s in data.get("services", [])],
            last_seen=float(data.get("last_seen", 0) or 0),
            note=data.get("note", ""),
            via=data.get("via", "ping"),
        )


@dataclass
class Favorite:
    ip: str
    mac: str = ""
    name: str = ""
    vendor: str = ""
    note: str = ""
    kind: str = "unknown"
    os_name: str = ""
    added: float = field(default_factory=time.time)
    last_seen: float = 0.0

    @property
    def key(self) -> str:
        return (self.mac or self.ip).upper()

    def matches(self, device: Device | None = None, *, ip: str = "", mac: str = "") -> bool:
        if device is not None:
            ip, mac = device.ip, device.mac
        if mac and self.mac:
            return self.mac.upper() == mac.upper()
        return bool(ip) and self.ip == ip

    def to_dict(self) -> dict[str, Any]:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "name": self.name,
            "vendor": self.vendor,
            "note": self.note,
            "kind": self.kind,
            "os_name": self.os_name,
            "added": self.added,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Favorite":
        return cls(
            ip=data.get("ip", ""),
            mac=data.get("mac", ""),
            name=data.get("name", ""),
            vendor=data.get("vendor", ""),
            note=data.get("note", ""),
            kind=data.get("kind", "unknown"),
            os_name=data.get("os_name", ""),
            added=float(data.get("added", 0) or 0),
            last_seen=float(data.get("last_seen", 0) or 0),
        )
