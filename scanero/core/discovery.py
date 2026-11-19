"""Passive name discovery helpers: mDNS (Avahi) and SSDP/UPnP."""
from __future__ import annotations

import re
import shutil
import socket
import subprocess
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

SSDP_ADDRESS = ("239.255.255.250", 1900)
MSEARCH = (
    "M-SEARCH * HTTP/1.1\r\n"
    "HOST: 239.255.255.250:1900\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: 2\r\n"
    "ST: ssdp:all\r\n"
    "USER-AGENT: Scanero/1.0 UPnP/1.1\r\n\r\n"
)


def _clean_name(value: str, limit: int = 64) -> str:
    value = value or ""
    value = re.sub(r"\\([0-9]{3})", lambda m: chr(int(m.group(1))), value)
    value = re.sub(r"\\(.)", r"\1", value)
    value = re.sub(r"\s+", " ", value).strip().strip('"')
    if len(value) > limit:
        value = value[: limit - 1].rstrip() + "…"
    return value


def _split_avahi(line: str) -> list[str]:
    """Split an avahi-browse parsable line, honouring escaped semicolons."""
    fields: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            buf.append(ch)
            buf.append(line[i + 1])
            i += 2
            continue
        if ch == ";":
            fields.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    fields.append("".join(buf))
    return fields


def mdns_discover(timeout: float = 2.6) -> dict[str, str]:
    """Return {ip: friendly_name} from resolved Avahi services.

    This is a single browse of the local mDNS domain rather than a reverse
    lookup per host, so it catches Apple/Android/IoT devices advertising
    AirPlay, Chromecast, printers and NAS services.
    """
    if not shutil.which("avahi-browse"):
        return {}
    try:
        proc = subprocess.Popen(
            ["avahi-browse", "--all", "--resolve", "--terminate", "--parsable"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return {}
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            out, _ = proc.communicate(timeout=1)
        except Exception:
            out = ""
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        return {}

    names: dict[str, str] = {}
    hostnames: dict[str, str] = {}
    for line in (out or "").splitlines():
        if not line.startswith("="):
            continue
        fields = _split_avahi(line)
        if len(fields) < 9:
            continue
        iface, proto = fields[1], fields[2]
        if proto != "IPv4":
            continue
        instance = _clean_name(fields[3])
        hostname = _clean_name(fields[6].rstrip("."), 80)
        address = fields[7].strip()
        try:
            socket.inet_aton(address)
        except OSError:
            continue
        if hostname:
            hostnames.setdefault(address, hostname.split(".")[0])
        if instance and instance not in ("_device-info",):
            names.setdefault(address, instance)

    for address, host in hostnames.items():
        names.setdefault(address, host)
    return names


def _parse_xml_location(location: str, timeout: float = 1.2) -> tuple[str, str, str]:
    try:
        with urlopen(location, timeout=timeout) as response:
            data = response.read(65536)
        root = ET.fromstring(data)
    except Exception:
        return "", "", ""

    values: dict[str, str] = {}
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower()
        text = (element.text or "").strip()
        if tag in ("friendlyname", "modelname", "manufacturer") and text:
            values.setdefault(tag, _clean_name(text, 80))
    return values.get("friendlyname", ""), values.get("modelname", ""), values.get("manufacturer", "")


def ssdp_discover(timeout: float = 2.6) -> dict[str, str]:
    """Return {ip: friendly_name} from UPnP/SSDP description documents."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(0.35)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.bind(("", 0))
        sock.sendto(MSEARCH.encode("ascii"), SSDP_ADDRESS)
    except Exception:
        sock.close()
        return {}

    locations: dict[str, str] = {}
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data, address = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except Exception:
            break
        text = data.decode("iso-8859-1", errors="ignore")
        headers: dict[str, str] = {}
        for line in text.splitlines()[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        location = headers.get("location", "")
        ip = address[0]
        if location.startswith(("http://", "https://")):
            locations.setdefault(ip, location)
    sock.close()

    if not locations:
        return {}

    results: dict[str, str] = {}
    workers = min(16, max(1, len(locations)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="scanero-ssdp") as executor:
        futures = {
            executor.submit(_parse_xml_location, location): ip
            for ip, location in locations.items()
        }
        for future in futures:
            ip = futures[future]
            try:
                friendly, model, manufacturer = future.result(timeout=1.8)
            except Exception:
                continue
            name = friendly or model
            if not name:
                continue
            if manufacturer and manufacturer.lower() not in name.lower() and len(name) < 28:
                name = f"{name} ({manufacturer})"
            results[ip] = _clean_name(name)
    return results


def discover_names(timeout: float = 2.6, use_mdns: bool = True, use_ssdp: bool = True) -> dict[str, str]:
    if not use_mdns and not use_ssdp:
        return {}
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="scanero-discovery") as executor:
        futures = []
        if use_mdns:
            futures.append(executor.submit(mdns_discover, timeout))
        if use_ssdp:
            futures.append(executor.submit(ssdp_discover, timeout))
        names: dict[str, str] = {}
        for future in futures:
            try:
                names.update(future.result(timeout=timeout + 1.5))
            except Exception:
                pass
    return names
