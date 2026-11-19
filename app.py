#!/usr/bin/env python3
"""Scanero IP scanner application entry point."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

# Make the font stack deterministic before QApplication is created.
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")


def _load_fonts() -> None:
    from PyQt6.QtGui import QFontDatabase

    fonts = BASE / "scanero" / "assets" / "fonts"
    for name in (
        "Inter-Regular.ttf",
        "Inter-Medium.ttf",
        "Inter-SemiBold.ttf",
        "Inter-Bold.ttf",
        "JetBrainsMono-Regular.ttf",
        "JetBrainsMono-Medium.ttf",
    ):
        path = fonts / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))


def _demo_devices():
    from scanero.core.models import Device, Service

    specs = [
        ("192.168.1.1", "Keenetic-Giga", "192.168.1.1", "A8:5E:45:11:22:33", "Keenetic Ltd.", "router", "Сетевая ОС",
         [Service(80, "http", "HTTP", "Keenetic Web", "http"), Service(443, "https", "HTTPS"),
          Service(22, "ssh", "SSH", "OpenSSH 9.6"), Service(53, "dns", "DNS")]),
        ("192.168.1.24", "DESKTOP-7K2M", "192.168.1.24", "3C:52:82:AA:10:24", "Hewlett Packard", "computer", "Windows",
         [Service(135, "rpc", "MS RPC"), Service(139, "netbios", "NetBIOS"),
          Service(445, "smb", "SMB"), Service(3389, "rdp", "RDP")]),
        ("192.168.1.41", "KM-35EEF6", "192.168.1.41", "00:17:C8:35:EE:F6", "KYOCERA Display Corporation", "printer", "Встроенная ОС",
         [Service(80, "http", "HTTP", "KM-MFP-http"), Service(443, "https", "HTTPS"),
          Service(515, "lpd", "LPD"), Service(631, "ipp", "IPP"), Service(9100, "printer", "RAW печать")]),
        ("192.168.1.56", "MacBook-Pro", "192.168.1.56", "F0:18:98:3C:56:01", "Apple, Inc.", "computer", "macOS",
         [Service(22, "ssh", "SSH", "OpenSSH 9.8"), Service(445, "smb", "SMB"), Service(548, "afp", "AFP")]),
        ("192.168.1.63", "SIP-W52P", "192.168.1.63", "00:15:65:F0:61:18", "XIAMEN YEALINK NETWORK", "phone", "Android",
         [Service(80, "http", "HTTP", "yealink embed httpd"), Service(443, "https", "HTTPS")]),
        ("192.168.1.77", "nas-home", "192.168.1.77", "00:11:32:78:9A:BC", "Synology Incorporated", "nas", "Linux",
         [Service(22, "ssh", "SSH", "OpenSSH 8.4"), Service(80, "http", "HTTP", "nginx"),
          Service(445, "smb", "SMB"), Service(5000, "http", "HTTP", "DSM")]),
        ("192.168.1.94", "ubuntu-dev", "192.168.1.94", "52:54:00:8E:22:94", "QEMU virtual NIC", "server", "Linux",
         [Service(22, "ssh", "SSH", "OpenSSH 9.6 Ubuntu"), Service(80, "http", "HTTP", "nginx"),
          Service(3000, "http", "HTTP", "Node.js"), Service(5432, "postgres", "PostgreSQL")]),
        ("192.168.1.108", "Samsung-TV", "192.168.1.108", "8C:79:F5:32:10:08", "Samsung Electronics", "tv", "Android",
         [Service(8001, "http", "HTTP"), Service(9197, "http", "HTTP")]),
        ("192.168.1.120", "WIN-SRV-01", "192.168.1.120", "00:25:90:92:80:0F", "Super Micro Computer", "server", "Windows",
         [Service(135, "rpc", "MS RPC"), Service(139, "netbios", "NetBIOS"),
          Service(445, "smb", "SMB"), Service(3389, "rdp", "RDP")]),
        ("192.168.1.142", "iPhone-Alex", "192.168.1.142", "D2:F7:CF:F2:3B:0B", "Локальный адрес", "phone", "iOS / iPadOS", []),
    ]
    devices = []
    for ip, name, hostname, mac, vendor, kind, os_name, services in specs:
        device = Device(
            ip=ip, name=name, hostname=hostname, mac=mac, vendor=vendor,
            kind=kind, os_name=os_name, status="online", services=services,
            ttl=64, last_seen=__import__("time").time(),
        )
        device.favorite = name in ("KM-35EEF6", "nas-home")
        devices.append(device)
    return devices


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--demo" in argv:
        os.environ["XDG_CONFIG_HOME"] = "/tmp/scanero-demo-config"
    elif "--screenshot" in argv and not os.environ.get("XDG_CONFIG_HOME"):
        os.environ["XDG_CONFIG_HOME"] = "/tmp/scanero-preview-config"
    if "--cli" in argv:
        from scanero.cli import main as cli_main
        idx = argv.index("--cli")
        return cli_main(argv[idx + 1:])
    if "--version" in argv:
        from scanero import __version__
        print(f"Scanero IP scanner {__version__}")
        return 0
    if "--help" in argv or "-h" in argv:
        print(
            "Scanero IP scanner — сканер локальной сети для Ubuntu\n\n"
            "Графический режим:      python3 app.py\n"
            "CLI:                    python3 app.py --cli --range 192.168.1.0/24 [--json out.json]\n"
            "Помощь по CLI:          python3 app.py --cli --help\n\n"
            "Служебные флаги демо/скриншотов: --demo --size 1460x900 --screenshot out.png"
        )
        return 0

    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication

    app = QApplication(argv)
    app.setApplicationName("Scanero")
    app.setOrganizationName("Scanero")
    app.setDesktopFileName("scanero")
    app.setStyle("Fusion")
    _load_fonts()
    base_font = QFont("Inter")
    base_font.setPixelSize(13)
    app.setFont(base_font)

    from scanero.ui.main_window import MainWindow

    window = MainWindow()
    if "--size" in argv:
        idx = argv.index("--size")
        try:
            w, h = argv[idx + 1].lower().split("x")
            window.resize(int(w), int(h))
        except Exception:
            pass
    window.show()

    if "--demo" in argv:
        for device in _demo_devices():
            window.scanner.on_found(device)
            window.scanner.on_updated(device)
        from scanero.core.scanner import ScanResult
        from scanero.core.models import Device
        demo = _demo_devices()
        known = {d.ip for d in demo}
        offline = [
            Device(ip=f"192.168.1.{i}", status="offline")
            for i in range(1, 255)
            if f"192.168.1.{i}" not in known
        ]
        result = ScanResult(
            range_expr="192.168.1.0/24",
            started=0,
            finished=4.2,
            target_count=254,
            online=len(demo),
            offline=len(offline),
            services=sum(len(d.services) for d in demo),
            devices=demo + offline,
        )
        for dev in demo:
            if dev.name in ("KM-35EEF6", "nas-home"):
                window.favorites.add(dev)
        window._refresh_favorites_ui()
        window.scanner.on_result(result)
        window.scanner.set_scanning(False)
        from scanero.core.storage import HistoryEntry
        import time as _time
        for age, count in ((0, 10), (3600 * 5, 8), (3600 * 27, 12)):
            window.history.add(HistoryEntry(
                id=str(int(_time.time() * 1000) + age),
                timestamp=_time.time() - age,
                range_expr="192.168.1.0/24",
                target_count=254,
                online=count,
                offline=254 - count,
                services=count * 3,
                duration=3.2 + count * 0.12,
                devices=[d.to_dict() for d in demo[:count]],
            ))
        window.history_page.refresh(window.history.items)
        from scanero.ui.widgets import plural
        window.scanner.status_label.setText(
            f"Сканирование завершено · {result.online} "
            f"{plural(result.online, 'устройство', 'устройства', 'устройств')} · "
            f"{result.services} {plural(result.services, 'сервис', 'сервиса', 'сервисов')}"
        )
        if len(window.scanner.model.devices()) > 5:
            window.scanner.tree.setCurrentIndex(window.scanner.proxy.index(1, 0))
        window._refresh_favorites_ui()
        from scanero.core.netinfo import Interface
        demo_iface = Interface(
            name="wlan0", ip="192.168.1.42", prefix=24,
            mac="A8:5E:45:11:22:33", wireless=True, ssid="HomeNet",
            is_default=True,
        )
        window.iface = demo_iface
        window.interfaces = [demo_iface]
        window.network_card.set_interface(demo_iface)
        window.scanner.set_interface(demo_iface, [demo_iface])
        window.scanner.range_edit.setText("192.168.1.0/24")
        if "--page" in argv:
            idx_page = argv.index("--page")
            if idx_page + 1 < len(argv):
                window.switch_page(argv[idx_page + 1])

    if "--screenshot" in argv:
        from PyQt6.QtCore import QTimer
        idx = argv.index("--screenshot")
        path = argv[idx + 1] if idx + 1 < len(argv) else "scanero-preview.png"

        def capture() -> None:
            pix = window.grab()
            pix.save(path)
            window.close()
            app.quit()

        QTimer.singleShot(900, capture)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
