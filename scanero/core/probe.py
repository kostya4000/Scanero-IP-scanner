"""Network probes: ICMP, hostnames, NetBIOS, banners and service discovery."""
from __future__ import annotations

import html
import ipaddress
import re
import socket
import ssl
import struct
import subprocess
import time
from typing import Iterable

from .models import Device, Service, STATUS_ONLINE
from .oui import lookup as oui_lookup, normalize_mac

# ---------------------------------------------------------------------------
# Basic probes
# ---------------------------------------------------------------------------


def tcp_open(ip: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((ip, port)) == 0
    except Exception:
        return False


def ping_host(ip: str, wait: float = 1.0) -> tuple[bool, int]:
    """ICMP echo. Returns (alive, ttl)."""
    wait_s = max(1, int(round(wait)))
    cmd = [
        "ping", "-4", "-n", "-q", "-c", "1",
        "-W", str(wait_s), "-w", str(wait_s + 1), ip,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=wait_s + 2, check=False
        )
    except Exception:
        return False, 0
    if proc.returncode != 0:
        return False, 0
    match = re.search(r"ttl=(\d+)", proc.stdout + proc.stderr, re.IGNORECASE)
    return True, int(match.group(1)) if match else 0


def reverse_dns(ip: str, timeout: float = 1.5) -> str:
    try:
        proc = subprocess.run(
            ["getent", "hosts", ip], capture_output=True, text=True, timeout=timeout, check=False
        )
    except Exception:
        return ""
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            name = parts[1].strip().rstrip(".")
            if name and name != ip:
                return name
    return ""


def mdns_lookup(ip: str, timeout: float = 1.5) -> str:
    try:
        proc = subprocess.run(
            ["avahi-resolve", "-a", ip], capture_output=True, text=True, timeout=timeout, check=False
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    out = proc.stdout.strip()
    if not out:
        return ""
    parts = out.split()
    name = parts[-1].strip().rstrip(".")
    if name and name != ip:
        return name
    return ""


# ---------------------------------------------------------------------------
# NetBIOS name service
# ---------------------------------------------------------------------------

def _encode_nb_name(name: bytes) -> bytes:
    if len(name) < 16:
        name = name + b"\x00" * (16 - len(name))
    out = bytearray()
    for byte in name[:16]:
        out.append(0x41 + ((byte >> 4) & 0x0F))
        out.append(0x41 + (byte & 0x0F))
    return bytes(out)


def netbios_lookup(ip: str, timeout: float = 1.0) -> dict[str, str]:
    """Query the NetBIOS node status (UDP/137) for a workstation name."""
    packet = (
        struct.pack(">HHHHHH", 0x4E53, 0x0000, 1, 0, 0, 0)
        + b"\x20"
        + _encode_nb_name(b"*" + b"\x00" * 15)
        + struct.pack(">HH", 0x0021, 0x0001)
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.sendto(packet, (ip, 137))
        data, _ = sock.recvfrom(2048)
    except Exception:
        return {}
    finally:
        sock.close()

    if len(data) < 12:
        return {}
    try:
        _, _, _, ancount, _, _ = struct.unpack(">HHHHHH", data[:12])
    except Exception:
        return {}
    if ancount < 1:
        return {}

    offset = 12
    # Skip the question section (encoded wildcard name + type/class).
    length = data[offset]
    offset += 1 + length + 1
    offset += 4

    names: list[dict] = []
    for _ in range(ancount):
        if offset >= len(data):
            break
        first = data[offset]
        if first & 0xC0 == 0xC0:
            offset += 2
        else:
            length = data[offset]
            offset += 1 + length + 1
        if offset + 10 > len(data):
            break
        rtype, _, _ttl, rdlen = struct.unpack(">HHIH", data[offset:offset + 10])
        offset += 10
        rdata = data[offset:offset + rdlen]
        offset += rdlen
        if rtype != 0x21 or not rdata:
            continue
        count = rdata[0]
        for idx in range(count):
            entry = rdata[1 + idx * 18: 1 + (idx + 1) * 18]
            if len(entry) < 18:
                break
            raw_name = entry[:15].decode("latin-1", errors="ignore").strip("\x00 ")
            suffix = entry[15]
            flags = struct.unpack(">H", entry[16:18])[0]
            if raw_name:
                names.append({
                    "name": raw_name,
                    "suffix": suffix,
                    "group": bool(flags & 0x8000),
                })
    if not names:
        return {}

    workstation = ""
    group = ""
    for item in names:
        if item["suffix"] == 0x00 and not item["group"] and not workstation:
            workstation = item["name"]
        if item["suffix"] in (0x00, 0x1C) and item["group"] and not group:
            group = item["name"]
    if not workstation:
        for item in names:
            if not item["group"]:
                workstation = item["name"]
                break
    return {"name": workstation, "workgroup": group}


# ---------------------------------------------------------------------------
# Banners / HTTP
# ---------------------------------------------------------------------------

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def http_probe(ip: str, port: int, tls: bool = False, timeout: float = 1.0) -> dict[str, str]:
    result = {"server": "", "title": "", "status": ""}
    sock = None
    try:
        raw = socket.create_connection((ip, port), timeout=timeout)
        raw.settimeout(timeout)
        if tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = ctx.wrap_socket(raw, server_hostname=ip)
        else:
            sock = raw
        request = (
            f"GET / HTTP/1.0\r\nHost: {ip}\r\n"
            "User-Agent: Scanero/1.0 (Ubuntu)\r\n"
            "Accept: text/html,*/*\r\nConnection: close\r\n\r\n"
        )
        sock.sendall(request.encode("ascii", errors="ignore"))
        chunks: list[bytes] = []
        total = 0
        while total < 30000:
            try:
                chunk = sock.recv(4096)
            except Exception:
                break
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if b"</title>" in b"".join(chunks).lower():
                break
        blob = b"".join(chunks)
        if not blob:
            return result
        head, _, body = blob.partition(b"\r\n\r\n")
        text = head.decode("iso-8859-1", errors="ignore")
        lines = text.splitlines()
        if lines:
            result["status"] = lines[0].strip()[:64]
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                if key.strip().lower() == "server":
                    result["server"] = value.strip()[:80]
        content = body.decode("utf-8", errors="ignore")
        match = _TITLE_RE.search(content)
        if match:
            title = html.unescape(_TAG_RE.sub(" ", match.group(1)))
            title = re.sub(r"\s+", " ", title).strip()
            result["title"] = title[:100]
    except Exception:
        pass
    finally:
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# SNMP sysName (v2c, community "public")
# ---------------------------------------------------------------------------

def _ber_len(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def _ber(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _ber_len(len(value)) + value


def _ber_int(value: int) -> bytes:
    if value == 0:
        return b"\x00"
    length = (value.bit_length() + 8) // 8
    return value.to_bytes(length, "big", signed=True)


def _ber_oid(oid: str) -> bytes:
    parts = [int(part) for part in oid.split(".")]
    encoded = bytearray([40 * parts[0] + parts[1]])
    for part in parts[2:]:
        if part == 0:
            encoded.append(0)
            continue
        chunks = []
        while part:
            chunks.append(part & 0x7F)
            part >>= 7
        for idx, chunk in enumerate(reversed(chunks)):
            encoded.append(chunk | (0x80 if idx < len(chunks) - 1 else 0))
    return bytes(encoded)


def _ber_read(data: bytes, offset: int) -> tuple[int, bytes, int]:
    tag = data[offset]
    offset += 1
    length = data[offset]
    offset += 1
    if length & 0x80:
        count = length & 0x7F
        length = int.from_bytes(data[offset:offset + count], "big")
        offset += count
    return tag, data[offset:offset + length], offset + length


def snmp_sysname(ip: str, community: str = "public", timeout: float = 0.6) -> str:
    """Read the SNMP sysName.0 scalar; works with v1/v2c agents."""
    request_id = int(time.time() * 1000) & 0x7FFFFFFF
    varbind = _ber(0x30, _ber(0x06, _ber_oid("1.3.6.1.2.1.1.5.0")) + _ber(0x05, b""))
    pdu = _ber(
        0xA0,
        _ber(0x02, _ber_int(request_id))
        + _ber(0x02, b"\x00")
        + _ber(0x02, b"\x00")
        + _ber(0x30, varbind),
    )
    message = _ber(
        0x30,
        _ber(0x02, b"\x01") + _ber(0x04, community.encode("utf-8")) + pdu,
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.sendto(message, (ip, 161))
        data, _ = sock.recvfrom(4096)
    except Exception:
        return ""
    finally:
        sock.close()
    try:
        _, content, _ = _ber_read(data, 0)  # message sequence
        offset = 0
        _, _, offset = _ber_read(content, offset)  # version
        _, _, offset = _ber_read(content, offset)  # community
        _, pdu_content, _ = _ber_read(content, offset)
        offset = 0
        _, _, offset = _ber_read(pdu_content, offset)  # request id
        _, _, offset = _ber_read(pdu_content, offset)  # error status
        _, _, offset = _ber_read(pdu_content, offset)  # error index
        _, vbl_content, _ = _ber_read(pdu_content, offset)
        _, varbind_content, _ = _ber_read(vbl_content, 0)
        offset = 0
        _, _, offset = _ber_read(varbind_content, offset)  # oid
        _, value, _ = _ber_read(varbind_content, offset)
        text = value.decode("utf-8", errors="ignore").strip()
        text = re.sub(r"\s+", " ", text)
        return text[:64]
    except Exception:
        return ""


def tls_cert_name(ip: str, port: int = 443, timeout: float = 1.0) -> str:
    """Return the certificate common name / first DNS SAN, if any."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((ip, port), timeout=timeout) as raw:
            raw.settimeout(timeout)
            with ctx.wrap_socket(raw, server_hostname=ip) as sock:
                cert = sock.getpeercert() or {}
        for rdn in cert.get("subject", ()):
            for key, value in rdn:
                if key == "commonName":
                    name = str(value).strip().strip("*.")
                    if name and not name.replace(".", "").isdigit():
                        return name[:64]
        for kind, value in cert.get("subjectAltName", ()):
            if kind == "DNS":
                name = str(value).strip().strip("*.")
                if name and not name.replace(".", "").isdigit():
                    return name[:64]
    except Exception:
        pass
    return ""


def banner_grab(ip: str, port: int, timeout: float = 0.8) -> str:
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            data = sock.recv(512)
        return data.decode("utf-8", errors="ignore").strip().splitlines()[0][:120]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Port scanning
# ---------------------------------------------------------------------------

HTTP_PORTS = {80, 5000, 8000, 8080, 8888, 631}
HTTPS_PORTS = {443, 8443}


def service_for_port(port: int) -> Service:
    return Service(port=port)


def scan_ports(
    ip: str,
    ports: Iterable[int],
    timeout: float = 0.35,
    banner: bool = True,
) -> list[Service]:
    found: list[Service] = []
    for port in sorted({int(p) for p in ports}):
        if not tcp_open(ip, port, timeout):
            continue
        service = service_for_port(port)
        if banner:
            if port in HTTP_PORTS:
                info = http_probe(ip, port, tls=False, timeout=min(1.2, max(0.6, timeout * 2)))
                service.product = info.get("server", "")
                service.title = info.get("title", "")
            elif port in HTTPS_PORTS:
                info = http_probe(ip, port, tls=True, timeout=min(1.4, max(0.7, timeout * 2)))
                service.product = info.get("server", "")
                service.title = info.get("title", "")
            elif service.kind in ("ssh", "ftp"):
                text = banner_grab(ip, port, timeout=min(1.0, max(0.5, timeout * 2)))
                if text:
                    service.product = _clean_banner(service.kind, text)
        found.append(service)
    return found


def _clean_banner(kind: str, text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if kind == "ssh":
        match = re.search(r"SSH-[\d.]+-([^\s]+)", text)
        if match:
            return match.group(1)[:80]
    if kind == "ftp" and text.startswith("220"):
        return text[3:].strip()[:80]
    return text[:80]


# ---------------------------------------------------------------------------
# Device classification
# ---------------------------------------------------------------------------

_PRINTER_VENDORS = (
    "hewlett", "hp inc", "canon", "epson", "brother", "xerox", "kyocera",
    "ricoh", "lexmark", "konica", "oki data", "zebra",
)
_ROUTER_VENDORS = (
    "tp-link", "mikrotik", "ubiquiti", "keenetic", "d-link", "netgear",
    "tenda", "cisco", "aruba", "linksys", "totolink", "mercusys", "arris",
    "technicolor", "sercomm", "edimax", "gl technologies", "gl.inet",
    "sagemcom", "calix", "juniper", "fortinet", "routerboard", "netis",
    "shenzhen gongjin", "zte", "fiberhome", "raisecom", "cdatatec",
)
_CAMERA_VENDORS = ("hikvision", "dahua", "axis communication", "uniview", "foscam", "reolink")
_NAS_VENDORS = ("synology", "qnap", "asustor", "buffalo", "western digital", "terra-master", "terramaster")
_PHONE_VENDORS = (
    "apple", "samsung", "xiaomi", "oneplus", "oppo", "vivo", "motorola",
    "realme", "nothing technology", "google", "yealink", "grandstream", "polycom",
)
_TV_VENDORS = ("lg electronics", "sony", "philips", "tcl", "hisense", "vestel")
_SERVER_HINTS = ("server", "srv", "proxmox", "esxi", "nas", "docker", "cloud")
_PC_NAME_HINTS = ("desktop-", "win-", "comp", "pc-", "notebook", "laptop", "macbook", "imac")
_ROUTER_NAME_HINTS = (
    "miwifi", "keenetic", "router", "gateway", "gpon", " access point",
    "openwrt", "routeros", "archer", "nighthawk", "fritz", "unifi", "airspan",
    "mikrotik", "dlink", "tp-link", "wifi", "wi-fi",
)


def guess_kind(device: Device) -> str:
    vendor = (device.vendor or "").lower()
    title = " ".join(s.title for s in device.services if s.title).lower()
    kinds = {s.kind for s in device.services}
    ports = {s.port for s in device.services}
    name = (device.name or device.hostname or "").lower()

    printer_hint = any(
        word in (name + " " + title + " " + vendor)
        for word in ("printer", "laserjet", "officejet", "ecotank", "mfp")
    )
    router_identity = (
        any(word in vendor for word in _ROUTER_VENDORS)
        or any(word in name + " " + title for word in _ROUTER_NAME_HINTS)
    )

    if any(word in vendor for word in _PRINTER_VENDORS) and printer_hint:
        return "printer"
    if ports & {554, 8554} or any(word in vendor for word in _CAMERA_VENDORS):
        return "camera"
    if any(word in vendor for word in _NAS_VENDORS):
        return "nas"
    if ports & {62078}:
        return "phone"
    # A router/AP can expose RAW printing (9100) as a USB print server;
    # its identity is stronger than the generic printer ports.
    if router_identity and not printer_hint and not (ports & {515, 631}):
        return "router"
    if ports & {9100, 515, 631}:
        return "printer"

    # Desktop-ish ports are the strongest signal and beat router vendors
    # (motherboard vendors are also present in home routers).
    if "smb" in kinds or "rdp" in kinds or "afp" in kinds or ports & {135, 139}:
        if any(word in (name + " " + vendor) for word in _SERVER_HINTS):
            return "server"
        return "computer"

    if any(word in name for word in _PC_NAME_HINTS):
        return "computer"
    if any(word in name for word in ("iphone", "redmi-", "poco-", "galaxy-", "pixel-", "oneplus")):
        return "tablet" if "ipad" in name else "phone"
    if "ipad" in name:
        return "tablet"
    if printer_hint:
        return "printer"
    if any(word in name for word in ("camera", "ipcam", "ipc-", "nvr-")):
        return "camera"
    if any(word in name for word in ("nas", "diskstation")):
        return "nas"
    if any(word in name for word in ("smart-tv", "bravia", "webos")) or name.endswith("-tv"):
        return "tv"

    if router_identity:
        return "router"

    if any(word in vendor for word in _TV_VENDORS):
        if any(word in name for word in ("tv", "bravia", "webos", "smart-tv")):
            return "tv"
        if "smb" not in kinds and "rdp" not in kinds and (device.os_name in ("Android", "iOS / iPadOS")):
            return "tv"

    if "ssh" in kinds and ("http" in kinds or "https" in kinds):
        if any(word in (name + " " + vendor) for word in _SERVER_HINTS):
            return "server"
        return "server" if "linux" in (device.os_name or "").lower() else "computer"
    if "ssh" in kinds:
        return "computer"
    if any(token in vendor for token in ("espressif", "tuya", "itead", "shelly", "sonoff")):
        return "iot"
    if any(word in vendor for word in _PHONE_VENDORS):
        return "phone"
    return "unknown"


def guess_os(device: Device) -> str:
    vendor = (device.vendor or "").lower()
    kinds = {s.kind for s in device.services}
    ports = {s.port for s in device.services}
    products = " ".join(s.product for s in device.services).lower()

    if any(token in products for token in ("ubuntu", "debian", "raspbian", "fedora", "centos", "alpine", "linux")):
        return "Linux"
    if "freebsd" in products:
        return "FreeBSD"
    if ports & {3389, 135}:
        return "Windows"
    if "smb" in kinds and device.ttl and 65 <= device.ttl <= 128:
        return "Windows"
    if "smb" in kinds and "windows" in products:
        return "Windows"
    name = (device.name or device.hostname or "").lower()
    if "apple" in vendor or "iphone" in name or "ipad" in name:
        if device.kind in ("phone", "tablet"):
            return "iOS / iPadOS"
        return "macOS"
    if "samsung" in vendor or "xiaomi" in vendor or any(
        token in name for token in ("redmi", "poco", "galaxy", "pixel", "oneplus", "honor")
    ):
        if device.kind in ("phone", "tablet", "tv"):
            return "Android"
    if device.kind == "printer":
        return "Встроенная ОС"
    if device.kind == "router":
        return "Сетевая ОС"
    if device.ttl:
        if device.ttl <= 64:
            return "Linux / Unix"
        if device.ttl <= 128:
            return "Windows"
        if device.ttl <= 255:
            return "Сетевое устройство"
    return ""


_GENERIC_TITLES = {
    "welcome", "login", "sign in", "index", "home", "dashboard", "web interface",
    "router", "admin", "iis windows server", "apache2 ubuntu default page",
    "test page", "document", "untitled", "redirect", "redirecting",
}


def _title_as_name(title: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip()
    if not title or len(title) > 48:
        return ""
    low = title.lower()
    if low in _GENERIC_TITLES:
        return ""
    if re.match(r"^[1-5]\d\d\b", low):
        return ""
    if any(word in low for word in (
        "login", "sign in", "welcome", "добро пожаловать", "default page",
        "moved permanently", "object moved", "not found", "forbidden",
        "unauthorized", "redirect",
    )):
        return ""
    if title.startswith(("http://", "https://", "192.", "10.", "172.")):
        return ""
    return title


def _short_hostname(name: str) -> str:
    name = (name or "").strip().rstrip(".")
    if not name:
        return ""
    short = name.split(".")[0]
    return short or name


def enrich_device(
    device: Device,
    options,
    neighbors: dict[str, dict[str, str]],
    pre_ports: Iterable[int] = (),
    local_macs: dict[str, str] | None = None,
    discovery_names: dict[str, str] | None = None,
) -> Device:
    device.status = STATUS_ONLINE
    device.last_seen = time.time()

    if local_macs and device.ip in local_macs:
        device.mac = local_macs[device.ip]
    if not device.mac and device.ip in neighbors:
        device.mac = neighbors[device.ip].get("mac", "")
    device.mac = normalize_mac(device.mac)
    if device.mac and not device.vendor:
        device.vendor = oui_lookup(device.mac)

    pre_ports = {int(p) for p in pre_ports}

    if getattr(options, "resolve_names", True):
        if getattr(options, "use_netbios", True):
            nb = netbios_lookup(device.ip)
            if nb:
                device.netbios = _short_hostname(nb.get("name", ""))
                device.workgroup = nb.get("workgroup", "")
        dns = reverse_dns(device.ip)
        if dns:
            device.hostname = dns
        if getattr(options, "use_mdns", True) and not dns:
            mdns = mdns_lookup(device.ip)
            if mdns:
                device.hostname = mdns

    if getattr(options, "scan_services", True):
        ports = list(getattr(options, "ports", [])) + list(pre_ports)
        services = scan_ports(
            device.ip,
            ports,
            timeout=float(getattr(options, "port_timeout", 0.35)),
        )
    else:
        services = [Service(port=p) for p in sorted(pre_ports)]

    # Merge duplicate ports, keeping the richest information.
    merged: dict[int, Service] = {}
    for service in services:
        current = merged.get(service.port)
        if current is None or (service.product and not current.product):
            merged[service.port] = service
    device.services = sorted(merged.values(), key=lambda s: s.port)

    friendly = (discovery_names or {}).get(device.ip, "")
    if not device.name:
        if device.netbios:
            device.name = device.netbios
        elif friendly:
            device.name = friendly
        elif device.hostname:
            device.name = _short_hostname(device.hostname)
        else:
            for service in device.services:
                if service.kind in ("https",) or service.port in (443, 8443):
                    cert_name = tls_cert_name(device.ip, service.port)
                    if cert_name:
                        device.name = cert_name
                        break
                candidate = _title_as_name(service.title)
                if candidate:
                    device.name = candidate
                    break
    if not device.name and getattr(options, "use_snmp", True):
        sysname = snmp_sysname(device.ip)
        if sysname:
            device.name = sysname

    device.kind = guess_kind(device)
    device.os_name = guess_os(device)
    return device


def probe_alive(ip: str, timeout: float = 1.0, tcp_discovery: bool = True) -> tuple[bool, int, str, list[int]]:
    """Quick liveness check: ICMP first, then a few common TCP ports."""
    alive, ttl = ping_host(ip, timeout)
    if alive:
        return True, ttl, "ping", []
    if tcp_discovery:
        open_ports: list[int] = []
        for port in (445, 3389, 22, 80, 443, 8080, 9100, 631):
            if tcp_open(ip, port, min(0.22, max(0.12, timeout / 3))):
                open_ports.append(port)
                # Continue a little: knowing two services immediately is useful.
                if len(open_ports) >= 2:
                    break
        if open_ports:
            return True, 0, "tcp", open_ports
    return False, 0, "", []


def ip_in_network(ip: str, network: str) -> bool:
    try:
        return ipaddress.IPv4Address(ip) in ipaddress.ip_network(network, strict=False)
    except Exception:
        return False
