"""Design tokens, light/dark palettes and the global stylesheet."""
from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass, fields


@dataclass
class Palette:
    mode: str = "dark"
    bg_top: str = "#070B13"
    bg_bottom: str = "#0A101D"
    sidebar_bg: str = "#090E19"
    sidebar_border: str = "#1C2A42"
    panel: str = "#0D1524"
    panel_soft: str = "#0B1220"
    card: str = "#0F1829"
    card_hover: str = "#131F34"
    card_active: str = "#142338"
    border: str = "#1C2A42"
    border_soft: str = "#162136"
    border_hover: str = "#243652"
    text: str = "#E8EEF9"
    text_soft: str = "#C9D7E8"
    muted: str = "#8A9DB5"
    dim: str = "#5D7089"
    accent: str = "#22D3EE"
    accent2: str = "#8B8CFF"
    accent_dark: str = "#0E7490"
    accent_soft: str = "#8CE8F7"
    green: str = "#3DDC97"
    red: str = "#FF6B7A"
    amber: str = "#FFC857"
    pink: str = "#F472B6"
    selection: str = "#12283C"
    white: str = "#FFFFFF"
    input_bg: str = "#0C1524"
    root_border: str = "#22334E"
    glow1: str = "#22D3EE"
    glow2: str = "#8B8CFF"
    grid: str = "#6784A8"
    track: str = "#18243A"
    toast_bg: str = "#0F192A"
    toast_border: str = "#2B3F5D"
    overlay_bg: str = "#101B2E"
    overlay_hover: str = "#0C1524"
    toggle_off: str = "#223148"
    badge_bg: str = "#2B3A52"
    knob: str = "#F2FAFF"
    close_icon: str = "#EDB5BC"
    hover_rgb: str = "#FFFFFF"
    scroll: str = "#25344B"
    scroll_hover: str = "#334560"
    primary_text: str = "#06121C"
    logo1: str = "#2BE0F5"
    logo2: str = "#4FA8FF"
    logo3: str = "#8B8CFF"
    dialog_bg: str = "#0B1320"


DARK = Palette()

LIGHT = Palette(
    mode="light",
    bg_top="#F6F9FE",
    bg_bottom="#EAF1FA",
    sidebar_bg="#FFFFFF",
    sidebar_border="#DCE5F1",
    panel="#FFFFFF",
    panel_soft="#F6F9FD",
    card="#FFFFFF",
    card_hover="#F2F7FE",
    card_active="#E8F3FB",
    border="#D3DEEB",
    border_soft="#E2EAF4",
    border_hover="#B9CADD",
    text="#0F1B2D",
    text_soft="#23364C",
    muted="#5D7089",
    dim="#8494A8",
    accent="#0891B2",
    accent2="#6366F1",
    accent_dark="#0E7490",
    accent_soft="#0E7490",
    green="#059669",
    red="#DC2626",
    amber="#B45309",
    pink="#DB2777",
    selection="#E0F2FE",
    input_bg="#F7FAFD",
    root_border="#C9D7E6",
    glow1="#0891B2",
    glow2="#6366F1",
    grid="#A8B9CC",
    track="#E3EBF5",
    toast_bg="#FFFFFF",
    toast_border="#D6E1EE",
    overlay_bg="#F1F6FC",
    overlay_hover="#FFFFFF",
    toggle_off="#D4DFEC",
    badge_bg="#E6EEF8",
    knob="#FFFFFF",
    close_icon="#B91C1C",
    hover_rgb="#0F1B2D",
    scroll="#C3D1E2",
    scroll_hover="#A9BED4",
    primary_text="#04121A",
    logo1="#0891B2",
    logo2="#3B82F6",
    logo3="#6366F1",
    dialog_bg="#FFFFFF",
)

P = Palette(**asdict(DARK))

DARK_KIND_COLORS = {
    "router": "#8B8CFF",
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
LIGHT_KIND_COLORS = {
    "router": "#6366F1",
    "computer": "#0891B2",
    "server": "#7C3AED",
    "printer": "#B45309",
    "phone": "#059669",
    "tablet": "#059669",
    "tv": "#DB2777",
    "camera": "#EA580C",
    "nas": "#0284C7",
    "iot": "#64748B",
    "unknown": "#64748B",
}

DARK_SERVICE_COLORS = {
    "http": "#22D3EE",
    "https": "#34D399",
    "smb": "#FFC857",
    "ssh": "#8B8CFF",
    "rdp": "#F472B6",
    "ftp": "#FB923C",
    "ipp": "#FFC857",
    "printer": "#FFC857",
    "lpd": "#FFC857",
    "vnc": "#A78BFA",
    "afp": "#38BDF8",
    "rtsp": "#F87171",
    "netbios": "#94A3B8",
    "rpc": "#94A3B8",
    "dns": "#38BDF8",
    "telnet": "#FB923C",
    "iphone": "#3DDC97",
}
LIGHT_SERVICE_COLORS = {
    "http": "#0891B2",
    "https": "#059669",
    "smb": "#B45309",
    "ssh": "#6366F1",
    "rdp": "#DB2777",
    "ftp": "#EA580C",
    "ipp": "#B45309",
    "printer": "#B45309",
    "lpd": "#B45309",
    "vnc": "#7C3AED",
    "afp": "#0284C7",
    "rtsp": "#DC2626",
    "netbios": "#64748B",
    "rpc": "#64748B",
    "dns": "#0284C7",
    "telnet": "#EA580C",
    "iphone": "#059669",
}

KIND_COLORS = dict(DARK_KIND_COLORS)
SERVICE_COLORS = dict(DARK_SERVICE_COLORS)


def detect_system_mode() -> str:
    """Detect the current GNOME/GTK color scheme (then Qt as a fallback)."""
    theme = ""
    try:
        scheme = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip().strip("'").lower()
        if "dark" in scheme:
            return "dark"
        if "light" in scheme:
            return "light"
        theme = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip().strip("'").lower()
        dark_tokens = ("dark", "nokto", "night", "black", "dracula", "sweet")
        if theme:
            return "dark" if any(token in theme for token in dark_tokens) else "light"
    except Exception:
        pass
    gtk_theme = os.environ.get("GTK_THEME", "").lower()
    if "dark" in gtk_theme:
        return "dark"
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication

        hints = QGuiApplication.styleHints()
        scheme = hints.colorScheme() if hasattr(hints, "colorScheme") else None
        if scheme is not None:
            dark = getattr(Qt.ColorScheme, "Dark", None)
            light = getattr(Qt.ColorScheme, "Light", None)
            if dark is not None and scheme == dark:
                return "dark"
            if light is not None and scheme == light:
                return "light"
    except Exception:
        pass
    return "dark"


def set_theme(preference: str = "system") -> str:
    """Apply dark/light/system preference. Returns the resolved mode."""
    mode = detect_system_mode() if preference not in ("dark", "light") else preference
    source = LIGHT if mode == "light" else DARK
    for field in fields(P):
        setattr(P, field.name, getattr(source, field.name))
    KIND_COLORS.clear()
    KIND_COLORS.update(LIGHT_KIND_COLORS if mode == "light" else DARK_KIND_COLORS)
    SERVICE_COLORS.clear()
    SERVICE_COLORS.update(LIGHT_SERVICE_COLORS if mode == "light" else DARK_SERVICE_COLORS)
    return mode


def rgba(color: str, alpha: float) -> str:
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    try:
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    except Exception:
        return f"rgba(0, 0, 0, {alpha})"
    return f"rgba({r}, {g}, {b}, {alpha})"


def service_color(kind: str) -> str:
    return SERVICE_COLORS.get(kind, P.dim)


def kind_color(kind: str) -> str:
    return KIND_COLORS.get(kind, P.dim)


def qss() -> str:
    accent_soft = rgba(P.accent, 0.1)
    accent_border = rgba(P.accent, 0.26)
    accent_border_hover = rgba(P.accent, 0.42)
    hover = rgba(P.hover_rgb, 0.055)
    hover_soft = rgba(P.hover_rgb, 0.035)
    return f"""
    * {{
        outline: none;
    }}
    QWidget {{
        color: {P.text};
    }}
    QWidget#Root, QWidget#Content {{
        background: transparent;
    }}
    QFrame#Sidebar {{
        background: rgba({int(P.sidebar_bg.lstrip('#')[0:2], 16)}, {int(P.sidebar_bg.lstrip('#')[2:4], 16)}, {int(P.sidebar_bg.lstrip('#')[4:6], 16)}, 0.82);
        border: 1px solid {P.sidebar_border};
        border-radius: 14px;
    }}
    QFrame#TitleBar {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {rgba(P.border, 0.55)};
    }}
    QFrame#Card, QFrame#Panel {{
        background: {rgba(P.card, 0.92)};
        border: 1px solid {P.border_soft};
        border-radius: 16px;
    }}
    QFrame#PanelSolid {{
        background: {P.panel};
        border: 1px solid {P.border_soft};
        border-radius: 16px;
    }}
    QFrame#Divider {{
        background: {P.border_soft};
        border: none;
        max-height: 1px;
        min-height: 1px;
    }}
    QLabel {{
        background: transparent;
        border: none;
    }}
    QLabel[role="eyebrow"] {{
        color: {P.accent};
        font-size: 10px;
        font-weight: 600;
    }}
    QLabel[role="h1"] {{
        color: {P.text};
        font-size: 24px;
        font-weight: 600;
    }}
    QLabel[role="h2"] {{
        color: {P.text};
        font-size: 17px;
        font-weight: 600;
    }}
    QLabel[role="muted"] {{
        color: {P.muted};
    }}
    QLabel[role="dim"] {{
        color: {P.dim};
    }}
    QLabel[role="value"] {{
        color: {P.text};
        font-size: 13px;
        font-weight: 500;
    }}
    QLabel[role="mono"] {{
        font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
        font-size: 12px;
        color: {P.text_soft};
    }}

    QLineEdit {{
        background: {P.input_bg};
        border: 1px solid {P.border_soft};
        border-radius: 10px;
        padding: 8px 12px;
        color: {P.text};
        selection-background-color: {rgba(P.accent, 0.32)};
        selection-color: {P.text};
    }}
    QLineEdit:hover {{
        border-color: {P.border};
    }}
    QLineEdit:focus {{
        border-color: {rgba(P.accent, 0.7)};
        background: {P.input_bg};
    }}
    QLineEdit[mono="true"] {{
        font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
        font-size: 12px;
    }}

    QPushButton {{
        background: {P.card};
        border: 1px solid {P.border_soft};
        border-radius: 10px;
        padding: 9px 16px;
        color: {P.text_soft};
        font-size: 12.5px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background: {P.card_hover};
        border-color: {P.border_hover};
        color: {P.text};
    }}
    QPushButton:pressed {{
        background: {P.panel_soft};
    }}
    QPushButton:disabled {{
        color: {P.dim};
        background: {P.panel_soft};
        border-color: {P.border_soft};
    }}
    QPushButton[variant="primary"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {P.accent}, stop:0.55 {P.logo2}, stop:1 {P.accent2});
        color: {P.primary_text};
        border: none;
        font-weight: 600;
        font-size: 13px;
        padding: 11px 20px;
    }}
    QPushButton[variant="primary"]:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {P.logo1}, stop:0.55 {P.logo2}, stop:1 {P.accent2});
    }}
    QPushButton[variant="primary"]:pressed {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {P.accent_dark}, stop:0.55 {P.accent}, stop:1 {P.accent2});
    }}
    QPushButton[variant="primary"]:disabled {{
        background: {P.card};
        color: {P.dim};
    }}
    QPushButton[variant="danger"] {{
        background: {rgba(P.red, 0.1)};
        border: 1px solid {rgba(P.red, 0.28)};
        color: {P.red};
    }}
    QPushButton[variant="danger"]:hover {{
        background: {rgba(P.red, 0.17)};
        border-color: {rgba(P.red, 0.45)};
    }}
    QPushButton[variant="ghost"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {P.muted};
        padding: 8px 12px;
    }}
    QPushButton[variant="ghost"]:hover {{
        background: {hover};
        color: {P.text};
    }}
    QPushButton[variant="soft"] {{
        background: {rgba(P.accent, 0.08)};
        border: 1px solid {rgba(P.accent, 0.2)};
        color: {P.accent_soft};
    }}
    QPushButton[variant="soft"]:hover {{
        background: {rgba(P.accent, 0.14)};
        border-color: {rgba(P.accent, 0.35)};
    }}
    QPushButton[variant="icon"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 9px;
        padding: 4px;
    }}
    QPushButton[variant="icon"]:hover {{
        background: {hover};
    }}
    QPushButton[variant="window"] {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 0;
    }}
    QPushButton[variant="window"]:hover {{
        background: {hover};
    }}
    QPushButton[variant="close"] {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 0;
    }}
    QPushButton[variant="close"]:hover {{
        background: {rgba(P.red, 0.88)};
    }}

    QPushButton[chip="true"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 15px;
        padding: 6px 13px;
        color: {P.muted};
        font-size: 12px;
        font-weight: 500;
    }}
    QPushButton[chip="true"]:hover {{
        background: {hover};
        color: {P.text_soft};
    }}
    QPushButton[chip="true"]:checked {{
        background: {rgba(P.accent, 0.1)};
        border-color: {rgba(P.accent, 0.28)};
        color: {P.accent_soft};
    }}

    QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 9px;
        padding: 5px;
        color: {P.muted};
    }}
    QToolButton:hover {{
        background: {hover};
        color: {P.text};
    }}

    QComboBox {{
        background: {P.input_bg};
        border: 1px solid {P.border_soft};
        border-radius: 10px;
        padding: 8px 12px;
        color: {P.text_soft};
        min-width: 120px;
    }}
    QComboBox:hover {{
        border-color: {P.border};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background: {P.overlay_bg};
        border: 1px solid {P.border};
        border-radius: 10px;
        padding: 5px;
        selection-background-color: {P.selection};
        outline: none;
    }}

    QMenu {{
        background: {P.overlay_bg};
        border: 1px solid {P.border};
        border-radius: 12px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 8px 28px 8px 12px;
        border-radius: 7px;
        color: {P.text_soft};
        font-size: 12.5px;
    }}
    QMenu::item:selected {{
        background: {rgba(P.accent, 0.12)};
        color: {P.text};
    }}
    QMenu::separator {{
        height: 1px;
        background: {P.border_soft};
        margin: 5px 8px;
    }}
    QMenu::icon {{
        padding-left: 8px;
    }}

    QToolTip {{
        background: {P.overlay_bg};
        color: {P.text_soft};
        border: 1px solid {P.border};
        border-radius: 8px;
        padding: 6px 9px;
        font-size: 11.5px;
    }}

    QScrollArea, QScrollArea > QWidget > QWidget {{
        background: transparent;
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 11px;
        margin: 3px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {P.scroll};
        border-radius: 3.5px;
        min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {P.scroll_hover};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 2px 3px;
    }}
    QScrollBar::handle:horizontal {{
        background: {P.scroll};
        border-radius: 3px;
        min-width: 30px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    QTreeView {{
        background: transparent;
        border: none;
        show-decoration-selected: 0;
        alternate-background-color: transparent;
        selection-background-color: transparent;
    }}
    QTreeView::item {{
        background: transparent;
        border: none;
        padding: 0;
    }}
    QTreeView::branch {{
        background: transparent;
    }}
    QHeaderView {{
        background: transparent;
        border: none;
    }}
    QHeaderView::section {{
        background: transparent;
        border: none;
        padding: 0;
    }}

    QSlider::groove:horizontal {{
        height: 4px;
        background: {P.track};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {P.accent}, stop:1 {P.accent2});
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {P.knob};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
        border: 2px solid {P.accent};
    }}
    QSlider::handle:horizontal:hover {{
        background: {P.white};
    }}

    QDialog, QMessageBox {{
        background: {P.dialog_bg};
    }}
    QMessageBox QLabel {{
        color: {P.text_soft};
        font-size: 13px;
    }}
    QMessageBox QPushButton {{
        min-width: 92px;
    }}
    QToolBar, QStatusBar {{
        background: transparent;
        border: none;
    }}
    """
