"""Desktop integrations: opening resources, terminals, Wake-on-LAN, shutdown."""
from __future__ import annotations

import shlex
import shutil
import socket
import struct
from typing import Callable

from PyQt6.QtCore import QProcess, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication

from .models import Device, Service, FILE_KINDS, TERMINAL_KINDS, WEB_KINDS


def notify(title: str, message: str) -> None:
    if shutil.which("notify-send"):
        QProcess.startDetached("notify-send", ["-a", "Scanero IP", "-i", "network-wireless", title, message])


def copy_text(text: str) -> None:
    QGuiApplication.clipboard().setText(text)


def device_as_text(device: Device) -> str:
    services = ", ".join(f"{s.name}:{s.port}" for s in device.services)
    lines = [
        f"Имя: {device.name or '—'}",
        f"IP: {device.ip}",
        f"MAC: {device.mac or '—'}",
        f"Производитель: {device.vendor or '—'}",
        f"Тип: {device.kind_label}",
        f"ОС: {device.os_name or '—'}",
        f"Сервисы: {services or '—'}",
    ]
    return "\n".join(lines)


def _terminal_command(command: str) -> list[str]:
    script = f"{command}; echo; read -r -p 'Нажмите Enter, чтобы закрыть…' _"
    candidates = [
        ("gnome-terminal", ["gnome-terminal", "--", "bash", "-lc", script]),
        ("kgx", ["kgx", "--", "bash", "-lc", script]),
        ("konsole", ["konsole", "-e", "bash", "-lc", script]),
        ("xfce4-terminal", ["xfce4-terminal", "-e", f"bash -lc {shlex.quote(script)}"]),
        ("mate-terminal", ["mate-terminal", "-e", f"bash -lc {shlex.quote(script)}"]),
        ("tilix", ["tilix", "-e", f"bash -lc {shlex.quote(script)}"]),
        ("alacritty", ["alacritty", "-e", "bash", "-lc", script]),
        ("kitty", ["kitty", "bash", "-lc", script]),
        ("xterm", ["xterm", "-e", "bash", "-lc", script]),
    ]
    env_term = shutil.which("x-terminal-emulator")
    for binary, args in candidates:
        if shutil.which(binary):
            return args
    if env_term:
        return [env_term, "-e", "bash", "-lc", script]
    return []


def open_terminal(command: str) -> tuple[bool, str]:
    args = _terminal_command(command)
    if not args:
        return False, "Не найден терминал. Установите gnome-terminal или xterm."
    ok, _pid = QProcess.startDetached(args[0], args[1:])
    if not ok:
        return False, "Не удалось запустить терминал."
    return True, ""


def open_service(device: Device, service: Service) -> tuple[bool, str]:
    """Open a discovered resource using the best available desktop app."""
    kind = service.kind
    ip = device.ip
    if kind in WEB_KINDS or kind in FILE_KINDS:
        QDesktopServices.openUrl(QUrl(service.url(ip)))
        return True, ""
    if kind in TERMINAL_KINDS:
        return open_terminal(f"{kind} {shlex.quote(ip)}")
    if kind == "rdp":
        return open_rdp(ip, device.name or "")
    if kind == "vnc":
        if shutil.which("remmina"):
            ok, _ = QProcess.startDetached("remmina", ["-c", f"vnc://{ip}"])
            return (True, "") if ok else (False, "Не удалось запустить Remmina.")
        QDesktopServices.openUrl(QUrl(f"vnc://{ip}"))
        return True, ""
    if kind == "rtsp":
        for player in ("vlc", "mpv"):
            if shutil.which(player):
                if player == "vlc":
                    ok, _ = QProcess.startDetached("vlc", [service.url(ip)])
                else:
                    ok, _ = QProcess.startDetached("mpv", [service.url(ip)])
                return (True, "") if ok else (False, "Не удалось запустить плеер.")
        QDesktopServices.openUrl(QUrl(service.url(ip)))
        return True, ""
    if kind in ("ipp", "printer"):
        QDesktopServices.openUrl(QUrl(f"http://{ip}:631/"))
        return True, ""
    QDesktopServices.openUrl(QUrl(service.url(ip)))
    return True, ""


def open_web(device: Device, service: Service | None = None) -> tuple[bool, str]:
    if service is None or service.kind not in WEB_KINDS:
        service = next((s for s in device.services if s.kind in WEB_KINDS), None)
    if service is None:
        QDesktopServices.openUrl(QUrl(f"http://{device.ip}/"))
        return True, ""
    return open_service(device, service)


def open_rdp(ip: str, name: str = "") -> tuple[bool, str]:
    if shutil.which("remmina"):
        ok, _ = QProcess.startDetached("remmina", ["-c", f"rdp://{ip}"])
        return (True, "") if ok else (False, "Не удалось запустить Remmina.")
    if shutil.which("xfreerdp"):
        ok, _ = QProcess.startDetached("xfreerdp", [f"/v:{ip}", "/dynamic-resolution"])
        return (True, "") if ok else (False, "Не удалось запустить FreeRDP.")
    if shutil.which("rdesktop"):
        ok, _ = QProcess.startDetached("rdesktop", [ip])
        return (True, "") if ok else (False, "Не удалось запустить rdesktop.")
    QDesktopServices.openUrl(QUrl(f"rdp://{ip}"))
    return False, "RDP-клиент не найден. Установите Remmina или freerdp2-x11."


def open_smb(device: Device) -> tuple[bool, str]:
    QDesktopServices.openUrl(QUrl(f"smb://{device.ip}/"))
    return True, ""


def open_ftp(device: Device) -> tuple[bool, str]:
    for service in device.services:
        if service.kind == "ftp":
            QDesktopServices.openUrl(QUrl(service.url(device.ip)))
            return True, ""
    QDesktopServices.openUrl(QUrl(f"ftp://{device.ip}/"))
    return True, ""


def ping_device(ip: str) -> tuple[bool, str]:
    return open_terminal(f"ping {shlex.quote(ip)}")


def trace_device(ip: str) -> tuple[bool, str]:
    tracer = "tracepath" if shutil.which("tracepath") else ("traceroute" if shutil.which("traceroute") else "")
    if not tracer:
        return False, "Утилита traceroute не установлена."
    return open_terminal(f"{tracer} {shlex.quote(ip)}")


def ssh_device(ip: str) -> tuple[bool, str]:
    return open_terminal(f"ssh {shlex.quote(ip)}")


# ---------------------------------------------------------------------------
# Wake-on-LAN
# ---------------------------------------------------------------------------

def send_wol(mac: str, broadcast: str = "255.255.255.255") -> tuple[bool, str]:
    cleaned = "".join(ch for ch in mac if ch in "0123456789abcdefABCDEF")
    if len(cleaned) != 12:
        return False, "Некорректный MAC-адрес"
    payload = b"\xff" * 6 + bytes.fromhex(cleaned) * 16
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(payload, (broadcast, 9))
            sock.sendto(payload, (broadcast, 7))
        return True, "Magic-пакет отправлен"
    except Exception as exc:
        return False, f"Не удалось отправить пакет: {exc}"


# ---------------------------------------------------------------------------
# Remote shutdown (Windows / Samba)
# ---------------------------------------------------------------------------

def remote_shutdown_supported() -> bool:
    return shutil.which("net") is not None


def run_remote_shutdown(
    host: str,
    username: str,
    password: str,
    *,
    reboot: bool = False,
    force: bool = True,
    message: str = "",
    delay: int = 0,
    on_finished: Callable[[bool, str], None] | None = None,
) -> QProcess | None:
    if not remote_shutdown_supported():
        return None
    args: list[str] = [
        "rpc", "shutdown",
        "-I", host,
        "-U", f"{username}%{password}",
    ]
    if force:
        args.append("-f")
    if reboot:
        args.append("-r")
    if delay > 0:
        args.extend(["-t", str(int(delay))])
    if message:
        args.extend(["-C", message])

    proc = QProcess()
    proc.setProgram("net")
    proc.setArguments(args)

    def _done(code: int, _status) -> None:
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", errors="ignore").strip()
        err = bytes(proc.readAllStandardError()).decode("utf-8", errors="ignore").strip()
        text = "\n".join(part for part in (out, err) if part).strip()
        if on_finished:
            on_finished(code == 0, text or ("Команда выполнена" if code == 0 else "Не удалось выполнить команду"))

    def _error(_err) -> None:
        if on_finished:
            on_finished(False, proc.errorString())

    proc.finished.connect(_done)
    proc.errorOccurred.connect(_error)
    proc.start()
    if not proc.waitForStarted(1500):
        if on_finished:
            on_finished(False, "Не удалось запустить net rpc shutdown")
        return None
    return proc
