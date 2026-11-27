"""Desktop integrations: opening resources, terminals, Wake-on-LAN, shutdown."""
from __future__ import annotations

import shlex
import shutil
import socket
import struct
import subprocess
import threading
import time
from typing import Callable

from PyQt6.QtCore import QProcess, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication

from ..i18n import tr, translate_text
from .models import Device, Service, FILE_KINDS, TERMINAL_KINDS, WEB_KINDS


def notify(title: str, message: str) -> None:
    if shutil.which("notify-send"):
        QProcess.startDetached("notify-send", [
            "-a", "Scanero IP", "-i", "network-wireless",
            translate_text(title), translate_text(message),
        ])


def copy_text(text: str) -> None:
    QGuiApplication.clipboard().setText(text)


def device_as_text(device: Device) -> str:
    services = ", ".join(f"{s.display_name}:{s.port}" for s in device.services)
    lines = [
        f"{tr('Имя')}: {device.name or '—'}",
        f"IP: {device.ip}",
        f"MAC: {device.mac or '—'}",
        f"{tr('Производитель')}: {device.vendor or '—'}",
        f"{tr('Тип')}: {device.kind_label}",
        f"{tr('ОС')}: {device.os_label or '—'}",
        f"{tr('Сервисы')}: {services or '—'}",
    ]
    return "\n".join(lines)


def _terminal_command(command: str) -> list[str]:
    prompt = translate_text("Нажмите Enter, чтобы закрыть…")
    script = f"{command}; echo; read -r -p {shlex.quote(prompt)} _"
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


# ---------------------------------------------------------------------------
# Bringing newly opened windows to the foreground
# ---------------------------------------------------------------------------

def _x11_windows_raw() -> set[str]:
    if not shutil.which("xdotool"):
        return set()
    try:
        proc = subprocess.run(
            ["xdotool", "search", "--onlyvisible", "--name", ".*"],
            capture_output=True, text=True, timeout=1.5,
        )
        return {token for token in proc.stdout.split() if token.isdigit()}
    except Exception:
        return set()


def _x11_windows() -> set[str]:
    if QGuiApplication.platformName() != "xcb":
        return set()
    return _x11_windows_raw()


def _activate_window(window_id: str) -> None:
    for cmd in (
        ["xdotool", "windowmap", window_id],
        ["xdotool", "windowactivate", window_id],
        ["xdotool", "windowraise", window_id],
    ):
        try:
            subprocess.run(cmd, capture_output=True, timeout=1.5)
        except Exception:
            pass


def _matching_windows_raw(hints: tuple[str, ...]) -> list[str]:
    if not shutil.which("xdotool"):
        return []
    found: set[str] = set()
    for hint in hints:
        for flag in ("--class", "--name"):
            try:
                proc = subprocess.run(
                    ["xdotool", "search", flag, hint],
                    capture_output=True, text=True, timeout=1.5,
                )
                found.update(token for token in proc.stdout.split() if token.isdigit())
            except Exception:
                pass
    return sorted(found, key=int)


def _focus_after(before: set[str], hints: tuple[str, ...] = ()) -> None:
    """Raise/focus newly opened windows without blocking the UI thread."""
    if QGuiApplication.platformName() != "xcb" or not shutil.which("xdotool"):
        return

    def worker() -> None:
        last = 0.0
        # If a new window is found, focus it once and stop. Otherwise retry and
        # eventually fall back to an already running handler (browser/file manager).
        for attempt, delay in enumerate((0.8, 2.0, 3.4)):
            time.sleep(max(0.0, delay - last))
            last = delay
            after = _x11_windows_raw()
            new = sorted(after - before, key=int)
            targets = new[-2:]
            if not targets and attempt >= 1:
                targets = _matching_windows_raw(hints)[-2:]
            if targets:
                for window_id in reversed(targets):
                    _activate_window(window_id)
                break

    threading.Thread(target=worker, name="scanero-window-focus", daemon=True).start()


def _scheme_hints(scheme: str) -> tuple[str, ...]:
    mapping = (
        ("google-chrome", ("google-chrome", "chrome")),
        ("chromium", ("chromium", "chrome")),
        ("firefox", ("firefox", "navigator")),
        ("nautilus", ("nautilus", "org.gnome.nautilus")),
        ("remmina", ("remmina",)),
        ("epiphany", ("epiphany",)),
        ("brave", ("brave",)),
        ("vlc", ("vlc",)),
        ("thunar", ("thunar",)),
        ("dolphin", ("dolphin",)),
    )
    try:
        desktop = subprocess.run(
            ["xdg-mime", "query", "default", f"x-scheme-handler/{scheme}"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip().lower()
    except Exception:
        desktop = ""
    for marker, hints in mapping:
        if marker in desktop:
            return hints
    fallback = {
        "http": ("google-chrome", "chrome", "chromium", "firefox"),
        "https": ("google-chrome", "chrome", "chromium", "firefox"),
        "smb": ("nautilus", "org.gnome.nautilus", "thunar", "dolphin"),
        "ftp": ("nautilus", "org.gnome.nautilus", "firefox"),
        "rdp": ("remmina",),
        "vnc": ("remmina",),
    }
    return fallback.get(scheme, ())


def open_external_url(url: str, hints: tuple[str, ...] | None = None) -> tuple[bool, str]:
    """Open a URL and raise/focus the window that handles it."""
    before = _x11_windows()
    ok = QDesktopServices.openUrl(QUrl(url))
    if not ok:
        return False, "Не найден обработчик для этой ссылки"
    _focus_after(before, hints if hints is not None else _scheme_hints(QUrl(url).scheme()))
    return True, ""


def _open_file_url(url: str) -> tuple[bool, str]:
    """Open smb://, ftp:// etc. in the file manager and focus it."""
    before = _x11_windows()
    if shutil.which("nautilus"):
        ok, _ = QProcess.startDetached("nautilus", ["--new-window", url])
        if ok:
            _focus_after(before, ("nautilus", "org.gnome.nautilus"))
            return True, ""
    ok, _ = open_external_url(url, ("nautilus", "org.gnome.nautilus", "thunar", "dolphin"))
    return (True, "") if ok else (False, "Не удалось открыть ресурс")


def open_terminal(command: str) -> tuple[bool, str]:
    args = _terminal_command(command)
    if not args:
        return False, "Не найден терминал. Установите gnome-terminal или xterm."
    before = _x11_windows()
    ok, _pid = QProcess.startDetached(args[0], args[1:])
    if not ok:
        return False, "Не удалось запустить терминал."
    terminal_name = args[0].rsplit("/", 1)[-1]
    hints = tuple(x for x in (
        terminal_name, "terminal", "gnome-terminal", "gnome-terminal-server",
        "konsole", "xterm", "alacritty", "kitty",
    ) if x)
    _focus_after(before, hints)
    return True, ""


def open_service(device: Device, service: Service) -> tuple[bool, str]:
    """Open a discovered resource using the best available desktop app."""
    kind = service.kind
    ip = device.ip
    if kind in WEB_KINDS:
        return open_external_url(service.url(ip))
    if kind in FILE_KINDS:
        return _open_file_url(service.url(ip))
    if kind in TERMINAL_KINDS:
        return open_terminal(f"{kind} {shlex.quote(ip)}")
    if kind == "rdp":
        return open_rdp(ip, device.name or "")
    if kind == "vnc":
        if shutil.which("remmina"):
            before = _x11_windows()
            ok, _ = QProcess.startDetached("remmina", ["-c", f"vnc://{ip}"])
            if ok:
                _focus_after(before, ("remmina",))
            return (True, "") if ok else (False, "Не удалось запустить Remmina.")
        return open_external_url(f"vnc://{ip}")
    if kind == "rtsp":
        for player in ("vlc", "mpv"):
            if shutil.which(player):
                before = _x11_windows()
                ok, _ = QProcess.startDetached(player, [service.url(ip)])
                if ok:
                    _focus_after(before, (player,))
                return (True, "") if ok else (False, "Не удалось запустить плеер.")
        return open_external_url(service.url(ip))
    if kind in ("ipp", "printer"):
        return open_external_url(f"http://{ip}:631/")
    return open_external_url(service.url(ip))


def open_web(device: Device, service: Service | None = None) -> tuple[bool, str]:
    if service is None or service.kind not in WEB_KINDS:
        service = next((s for s in device.services if s.kind in WEB_KINDS), None)
    if service is None:
        return open_external_url(f"http://{device.ip}/")
    return open_service(device, service)


def open_rdp(ip: str, name: str = "") -> tuple[bool, str]:
    if shutil.which("remmina"):
        before = _x11_windows()
        ok, _ = QProcess.startDetached("remmina", ["-c", f"rdp://{ip}"])
        if ok:
            _focus_after(before, ("remmina",))
        return (True, "") if ok else (False, "Не удалось запустить Remmina.")
    if shutil.which("xfreerdp"):
        before = _x11_windows()
        ok, _ = QProcess.startDetached("xfreerdp", [f"/v:{ip}", "/dynamic-resolution"])
        if ok:
            _focus_after(before, ("xfreerdp", "freerdp"))
        return (True, "") if ok else (False, "Не удалось запустить FreeRDP.")
    if shutil.which("rdesktop"):
        before = _x11_windows()
        ok, _ = QProcess.startDetached("rdesktop", [ip])
        if ok:
            _focus_after(before, ("rdesktop",))
        return (True, "") if ok else (False, "Не удалось запустить rdesktop.")
    return open_external_url(f"rdp://{ip}")


def open_smb(device: Device) -> tuple[bool, str]:
    return _open_file_url(f"smb://{device.ip}/")


def open_ftp(device: Device) -> tuple[bool, str]:
    for service in device.services:
        if service.kind == "ftp":
            return _open_file_url(service.url(device.ip))
    return _open_file_url(f"ftp://{device.ip}/")


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
