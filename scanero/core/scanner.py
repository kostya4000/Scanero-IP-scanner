"""High level network scan orchestration (UI agnostic)."""
from __future__ import annotations

import ipaddress
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .models import Device, STATUS_OFFLINE, STATUS_ONLINE
from .netinfo import Interface, list_interfaces, local_mac_map, neighbor_table
from .probe import enrich_device, probe_alive
from .oui import lookup as vendor_lookup

DEFAULT_PORTS = [
    21, 22, 23, 53, 80, 135, 139, 443, 445, 515, 554, 631,
    3389, 5000, 5900, 8080, 8443, 9100,
]

EventCallback = Callable[[str, object], None]


@dataclass
class ScanOptions:
    threads: int = 96
    ping_timeout: float = 1.0
    port_timeout: float = 0.35
    scan_services: bool = True
    resolve_names: bool = True
    use_netbios: bool = True
    use_mdns: bool = True
    tcp_discovery: bool = True
    ports: list[int] = field(default_factory=lambda: list(DEFAULT_PORTS))
    interfaces: list[Interface] = field(default_factory=list)

    @property
    def workers(self) -> int:
        return max(4, min(256, int(self.threads)))


@dataclass
class ScanResult:
    range_expr: str
    started: float
    finished: float
    target_count: int
    online: int
    offline: int
    services: int
    devices: list[Device]
    cancelled: bool = False

    @property
    def duration(self) -> float:
        return max(0.0, self.finished - self.started)


def _emit(callback: EventCallback | None, kind: str, payload: object) -> None:
    if callback is not None:
        try:
            callback(kind, payload)
        except Exception:
            pass


def scan_network(
    targets: Iterable[ipaddress.IPv4Address | str],
    options: ScanOptions | None = None,
    range_expr: str = "",
    on_event: EventCallback | None = None,
    stop_event: threading.Event | None = None,
) -> ScanResult:
    options = options or ScanOptions()
    stop_event = stop_event or threading.Event()
    started = time.time()

    ips = [str(t) for t in targets]
    total = len(ips)
    interfaces = options.interfaces or list_interfaces()
    local_macs = local_mac_map(interfaces)
    local_hostname = socket.gethostname()
    local_ips = set(local_macs)
    neighbors_before = neighbor_table()

    alive: dict[str, dict] = {}
    completed = 0
    last_progress = 0.0

    _emit(on_event, "phase", {"stage": "discover", "total": total})

    executor = ThreadPoolExecutor(max_workers=options.workers, thread_name_prefix="scanero-ping")
    futures = {
        executor.submit(probe_alive, ip, options.ping_timeout, options.tcp_discovery): ip
        for ip in ips
    }
    cancelled = False
    try:
        for future in as_completed(futures):
            if stop_event.is_set():
                cancelled = True
                break
            ip = futures[future]
            try:
                found, ttl, via, pre_ports = future.result()
            except Exception:
                found, ttl, via, pre_ports = False, 0, "", []
            completed += 1
            if found:
                device = Device(ip=ip, status=STATUS_ONLINE, ttl=ttl, via=via)
                if ip in local_ips:
                    device.name = local_hostname
                    device.hostname = socket.getfqdn()
                    device.mac = local_macs.get(ip, "")
                    device.vendor = vendor_lookup(device.mac)
                elif ip in neighbors_before:
                    device.mac = neighbors_before[ip].get("mac", "")
                    device.vendor = vendor_lookup(device.mac)
                alive[ip] = {
                    "device": device,
                    "pre_ports": list(pre_ports),
                    "via": via,
                    "ttl": ttl,
                }
                _emit(on_event, "found", device)

            now = time.time()
            if completed == total or now - last_progress > 0.06:
                last_progress = now
                _emit(on_event, "progress", {
                    "stage": "discover",
                    "done": completed,
                    "total": total,
                    "found": len(alive),
                })
    finally:
        executor.shutdown(wait=not cancelled, cancel_futures=cancelled)

    if cancelled:
        devices = sorted(
            (info["device"] for info in alive.values()),
            key=lambda d: tuple(int(x) for x in d.ip.split(".")),
        )
        finished = time.time()
        return ScanResult(
            range_expr=range_expr,
            started=started,
            finished=finished,
            target_count=total,
            online=len(devices),
            offline=0,
            services=0,
            devices=devices,
            cancelled=True,
        )

    # ------------------------------------------------------------------
    # ARP table: find hosts that ignore ICMP but still answer ARP.
    # ------------------------------------------------------------------
    neighbors = neighbor_table()
    for ip in ips:
        if ip in alive or ip not in neighbors:
            continue
        info = neighbors[ip]
        mac = info.get("mac", "")
        if not mac:
            continue
        device = Device(
            ip=ip,
            mac=mac,
            vendor=vendor_lookup(mac),
            status=STATUS_ONLINE,
            via="arp",
        )
        if ip in local_ips:
            device.name = local_hostname
            device.hostname = socket.getfqdn()
        alive[ip] = {"device": device, "pre_ports": [], "via": "arp", "ttl": 0}
        _emit(on_event, "found", device)

    # ------------------------------------------------------------------
    # Enrichment: names, MAC vendor, open services, classification.
    # ------------------------------------------------------------------
    online_count = len(alive)
    _emit(on_event, "phase", {"stage": "services", "total": online_count})

    devices_by_ip: dict[str, Device] = {}
    if online_count:
        executor = ThreadPoolExecutor(max_workers=options.workers, thread_name_prefix="scanero-enrich")
        futures = {}
        for ip, info in alive.items():
            futures[executor.submit(
                enrich_device,
                info["device"],
                options,
                neighbors,
                info["pre_ports"],
                local_macs,
            )] = ip
        completed = 0
        last_progress = 0.0
        try:
            for future in as_completed(futures):
                if stop_event.is_set():
                    cancelled = True
                    break
                ip = futures[future]
                completed += 1
                try:
                    device = future.result()
                except Exception:
                    device = alive[ip]["device"]
                devices_by_ip[ip] = device
                _emit(on_event, "updated", device)
                now = time.time()
                if completed == online_count or now - last_progress > 0.06:
                    last_progress = now
                    _emit(on_event, "progress", {
                        "stage": "services",
                        "done": completed,
                        "total": online_count,
                        "found": online_count,
                    })
        finally:
            executor.shutdown(wait=not cancelled, cancel_futures=cancelled)

    if cancelled:
        devices = list(devices_by_ip.values())
        for info in alive.values():
            if info["device"].ip not in devices_by_ip:
                devices.append(info["device"])
        devices.sort(key=lambda d: tuple(int(x) for x in d.ip.split(".")))
        finished = time.time()
        return ScanResult(
            range_expr=range_expr,
            started=started,
            finished=finished,
            target_count=total,
            online=len(devices),
            offline=max(0, total - len(devices)),
            services=sum(len(d.services) for d in devices),
            devices=devices,
            cancelled=True,
        )

    # ------------------------------------------------------------------
    # Add offline addresses so the "all addresses" filter is complete.
    # ------------------------------------------------------------------
    offline_devices: list[Device] = []
    for ip in ips:
        if ip in devices_by_ip or ip in alive:
            continue
        offline_devices.append(
            Device(ip=ip, status=STATUS_OFFLINE, via="", last_seen=time.time())
        )
    devices = list(devices_by_ip.values())
    for info in alive.values():
        if info["device"].ip not in devices_by_ip:
            devices.append(enrich_device(info["device"], options, neighbors, info["pre_ports"], local_macs))
    devices.extend(offline_devices)
    devices.sort(key=lambda d: tuple(int(x) for x in d.ip.split(".")))

    online = sum(1 for d in devices if d.status == STATUS_ONLINE)
    services = sum(len(d.services) for d in devices if d.status == STATUS_ONLINE)
    finished = time.time()

    return ScanResult(
        range_expr=range_expr,
        started=started,
        finished=finished,
        target_count=total,
        online=online,
        offline=max(0, total - online),
        services=services,
        devices=devices,
        cancelled=False,
    )
