"""Local network discovery and IP range parsing."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import subprocess
from dataclasses import dataclass

from ..i18n import current_language

MAX_TARGETS = 65536
SOFT_LIMIT = 4096

VIRTUAL_PREFIXES = (
    "docker", "br-", "virbr", "veth", "vnet", "tun", "tap", "lxc", "lxd",
    "podman", "cni", "flannel", "zt", "tailscale", "wg",
)


def _run(cmd: list[str], timeout: float = 4.0) -> str:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.stdout.strip()
    except Exception:
        return ""


@dataclass
class Interface:
    name: str
    ip: str
    prefix: int
    mac: str = ""
    wireless: bool = False
    ssid: str = ""
    is_default: bool = False
    virtual: bool = False

    @property
    def subnet(self) -> str:
        try:
            return str(ipaddress.ip_network(f"{self.ip}/{self.prefix}", strict=False))
        except Exception:
            return f"{self.ip}/24"

    @property
    def default_range(self) -> str:
        """A comfortable /24 (or the real subnet when it is smaller)."""
        try:
            net = ipaddress.ip_network(f"{self.ip}/{self.prefix}", strict=False)
            if net.prefixlen >= 24 or net.num_addresses <= 256:
                return str(net)
            return str(ipaddress.ip_network(f"{self.ip}/24", strict=False))
        except Exception:
            return f"{self.ip}/24"

    @property
    def whole_subnet(self) -> str:
        return self.subnet

    @property
    def title(self) -> str:
        if self.wireless:
            return f"Wi-Fi · {self.name}"
        if self.virtual:
            return f"Виртуальный · {self.name}"
        return f"Ethernet · {self.name}"

    @property
    def subtitle(self) -> str:
        if self.wireless and self.ssid:
            return self.ssid
        return f"{self.ip}/{self.prefix}"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ip": self.ip,
            "prefix": self.prefix,
            "mac": self.mac,
            "wireless": self.wireless,
            "ssid": self.ssid,
            "is_default": self.is_default,
            "virtual": self.virtual,
            "default_range": self.default_range,
            "subnet": self.subnet,
        }


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except Exception:
        return ""


def _default_route_iface() -> str:
    raw = _run(["ip", "-j", "route", "show", "default"])
    if raw:
        try:
            data = json.loads(raw)
            for item in data:
                dev = item.get("dev")
                if dev:
                    return dev
        except Exception:
            pass
    raw = _run(["ip", "route", "show", "default"])
    m = re.search(r"\bdev\s+(\S+)", raw)
    return m.group(1) if m else ""


def _ssid(ifname: str) -> str:
    out = _run(["iwgetid", "-r", ifname], timeout=2)
    if out:
        return out.splitlines()[0].strip()
    out = _run(["nmcli", "-t", "-f", "GENERAL.CONNECTION", "device", "show", ifname], timeout=3)
    for line in out.splitlines():
        if line.startswith("GENERAL.CONNECTION:"):
            value = line.split(":", 1)[1].strip()
            if value and value != "--":
                return value
    return ""


def list_interfaces() -> list[Interface]:
    """Discover IPv4 interfaces, sorted with the most useful one first."""
    try:
        data = json.loads(_run(["ip", "-j", "addr", "show"]))
    except Exception:
        data = []

    default_iface = _default_route_iface()
    result: list[Interface] = []

    for item in data:
        name = item.get("ifname", "")
        if not name or name == "lo":
            continue
        for addr in item.get("addr_info", []):
            if addr.get("family") != "inet":
                continue
            ip = addr.get("local", "")
            if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                continue
            prefix = int(addr.get("prefixlen", 24))
            mac = _read(f"/sys/class/net/{name}/address")
            if not mac or mac == "00:00:00:00:00:00":
                mac = addr.get("address", "")
            wireless = bool(_read(f"/sys/class/net/{name}/wireless")) or name.startswith(("wl", "wlan"))
            virtual = name.startswith(VIRTUAL_PREFIXES)
            result.append(
                Interface(
                    name=name,
                    ip=ip,
                    prefix=prefix,
                    mac=mac.upper(),
                    wireless=wireless,
                    ssid=_ssid(name) if wireless else "",
                    is_default=(name == default_iface),
                    virtual=virtual,
                )
            )

    if not result:
        # Very small fallback when iproute2 is unavailable.
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if ip and not ip.startswith("127."):
                result.append(Interface(name="eth0", ip=ip, prefix=24, is_default=True))
        except Exception:
            pass

    def sort_key(iface: Interface) -> tuple:
        return (
            0 if iface.is_default else 1,
            0 if not iface.virtual else 1,
            0 if iface.wireless else 1,
            iface.name,
        )

    result.sort(key=sort_key)
    return result


def best_interface(interfaces: list[Interface] | None = None) -> Interface | None:
    if interfaces is None:
        interfaces = list_interfaces()
    return interfaces[0] if interfaces else None


# ---------------------------------------------------------------------------
# IP range parsing
# ---------------------------------------------------------------------------

def _parse_endpoint(token: str, start: ipaddress.IPv4Address) -> ipaddress.IPv4Address:
    token = token.strip()
    if token.isdigit():
        octets = str(start).split(".")
        octets[-1] = token
        return ipaddress.IPv4Address(".".join(octets))
    return ipaddress.IPv4Address(token)


def parse_targets(expr: str, interfaces: list[Interface] | None = None) -> list[ipaddress.IPv4Address]:
    """Expand an AIPS-style range expression into a list of IPv4 addresses.

    Supported forms:
      192.168.1.1-254
      192.168.1.10-192.168.1.50
      192.168.1.0/24
      192.168.1.*
      10.0.0.1, 10.0.0.8, 10.0.0.20-30
      wlp0s20f3            (an interface name)
    """
    text = (expr or "").strip()
    if not text:
        raise ValueError("Введите диапазон IP-адресов")

    text = text.replace("–", "-").replace("—", "-").replace(";", ",").replace("\n", ",")
    tokens = [t.strip() for t in re.split(r"[,\s]+", text) if t.strip()]
    if not tokens:
        raise ValueError("Введите диапазон IP-адресов")

    iface_map = {i.name.lower(): i for i in (interfaces or [])}
    collected: list[ipaddress.IPv4Address] = []
    seen: set[int] = set()

    def add(addr: ipaddress.IPv4Address) -> None:
        value = int(addr)
        if value not in seen:
            seen.add(value)
            collected.append(addr)
            if len(collected) > MAX_TARGETS:
                raise ValueError(f"Слишком большой диапазон (максимум {MAX_TARGETS} адресов)")

    for token in tokens:
        low = token.lower()
        if low in iface_map:
            iface = iface_map[low]
            net = ipaddress.ip_network(f"{iface.ip}/{iface.prefix}", strict=False)
            for host in net.hosts():
                add(host)
            continue

        if "/" in token:
            try:
                net = ipaddress.ip_network(token, strict=False)
            except ValueError as exc:
                raise ValueError(f"Некорректный диапазон: {token}") from exc
            if net.version != 4:
                raise ValueError("Поддерживаются только IPv4-адреса")
            for host in net.hosts():
                add(host)
            continue

        if "*" in token:
            if token.count("*") > 1:
                raise ValueError("Поддерживается только одна звёздочка в адресе")
            base = token.replace("*", "1")
            try:
                start_ip = ipaddress.IPv4Address(base)
            except ValueError as exc:
                raise ValueError(f"Некорректный адрес: {token}") from exc
            octets = str(start_ip).split(".")
            idx = token.split(".").index("*")
            if idx == 3:
                for last in range(1, 255):
                    octets[3] = str(last)
                    add(ipaddress.IPv4Address(".".join(octets)))
            else:
                raise ValueError("Маска вида 192.168.1.* поддерживается только для последнего октета")
            continue

        if "-" in token:
            start_s, end_s = token.split("-", 1)
            try:
                start_ip = ipaddress.IPv4Address(start_s.strip())
                end_ip = _parse_endpoint(end_s, start_ip)
            except ValueError as exc:
                raise ValueError(f"Некорректный диапазон: {token}") from exc
            if int(end_ip) < int(start_ip):
                raise ValueError(f"Конец диапазона меньше начала: {token}")
            for value in range(int(start_ip), int(end_ip) + 1):
                add(ipaddress.IPv4Address(value))
            continue

        try:
            add(ipaddress.IPv4Address(token))
        except ValueError as exc:
            raise ValueError(f"Некорректный IP-адрес: {token}") from exc

    if not collected:
        raise ValueError("Диапазон не содержит адресов")
    collected.sort(key=int)
    return collected


def _plural(n: int, one: str, few: str, many: str) -> str:
    if current_language() == "en":
        return one if n == 1 else many
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def describe_targets(targets: list[ipaddress.IPv4Address]) -> str:
    if not targets:
        return "—"
    if len(targets) == 1:
        return str(targets[0])
    first, last = targets[0], targets[-1]
    if int(last) - int(first) + 1 == len(targets):
        return f"{first} – {last}"
    return f"{len(targets)} {_plural(len(targets), 'адрес', 'адреса', 'адресов')}"


def interface_for_ip(ip: str, interfaces: list[Interface] | None = None) -> Interface | None:
    if interfaces is None:
        interfaces = list_interfaces()
    try:
        addr = ipaddress.IPv4Address(ip)
    except Exception:
        return None
    for iface in interfaces:
        try:
            net = ipaddress.ip_network(f"{iface.ip}/{iface.prefix}", strict=False)
        except Exception:
            continue
        if addr in net:
            return iface
    return None


# ---------------------------------------------------------------------------
# ARP / neighbour table
# ---------------------------------------------------------------------------

_MAC_RE = re.compile(r"([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}")


def neighbor_table() -> dict[str, dict[str, str]]:
    """Return {ip: {'mac': ..., 'state': ..., 'iface': ...}}."""
    result: dict[str, dict[str, str]] = {}
    raw = _run(["ip", "-4", "neigh", "show"], timeout=3)
    for line in raw.splitlines():
        parts = line.split()
        if not parts:
            continue
        ip = parts[0]
        try:
            ipaddress.IPv4Address(ip)
        except Exception:
            continue
        mac = ""
        iface = ""
        state = ""
        if "dev" in parts:
            idx = parts.index("dev")
            if idx + 1 < len(parts):
                iface = parts[idx + 1]
        if "lladdr" in parts:
            idx = parts.index("lladdr")
            if idx + 1 < len(parts):
                mac = parts[idx + 1].upper()
        for candidate in ("REACHABLE", "STALE", "DELAY", "PROBE", "PERMANENT", "NOARP", "FAILED", "INCOMPLETE"):
            if candidate in parts:
                state = candidate
                break
        if not mac or not _MAC_RE.fullmatch(mac):
            continue
        if state in ("FAILED", "INCOMPLETE"):
            continue
        result[ip] = {"mac": mac, "state": state, "iface": iface}

    if not result:
        # /proc/net/arp fallback
        try:
            with open("/proc/net/arp", "r", encoding="utf-8") as fh:
                next(fh, None)
                for line in fh:
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    ip, mac, flags = parts[0], parts[3].upper(), parts[2]
                    if flags == "0x0" or not _MAC_RE.fullmatch(mac):
                        continue
                    result[ip] = {"mac": mac, "state": "REACHABLE", "iface": parts[5] if len(parts) > 5 else ""}
        except Exception:
            pass
    return result


def local_mac_map(interfaces: list[Interface] | None = None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for iface in interfaces or list_interfaces():
        if iface.mac:
            mapping[iface.ip] = iface.mac.upper()
    return mapping


def is_local_network(ip: str, interfaces: list[Interface] | None = None) -> bool:
    return interface_for_ip(ip, interfaces) is not None
