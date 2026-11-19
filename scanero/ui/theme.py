"""Design tokens and global stylesheet."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg_top: str = "#070B13"
    bg_bottom: str = "#0A101D"
    sidebar: str = "#0A0F1A"
    panel: str = "#0D1524"
    panel_soft: str = "#0B1220"
    card: str = "#0F1829"
    card_hover: str = "#131F34"
    card_active: str = "#142338"
    border: str = "#1C2A42"
    border_soft: str = "#162136"
    text: str = "#E8EEF9"
    text_soft: str = "#C9D7E8"
    muted: str = "#8A9DB5"
    dim: str = "#5D7089"
    accent: str = "#22D3EE"
    accent2: str = "#8B8CFF"
    accent_dark: str = "#0E7490"
    green: str = "#3DDC97"
    red: str = "#FF6B7A"
    amber: str = "#FFC857"
    pink: str = "#F472B6"
    selection: str = "#12283C"
    white: str = "#FFFFFF"


P = Palette()

KIND_COLORS = {
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

SERVICE_COLORS = {
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


def service_color(kind: str) -> str:
    return SERVICE_COLORS.get(kind, "#7C8EA8")


def kind_color(kind: str) -> str:
    return KIND_COLORS.get(kind, "#64748B")


def qss() -> str:
    return f"""
    * {{
        outline: none;
    }}
    QWidget {{
        color: {P.text};
    }}
    QWidget#Root {{
        background: transparent;
    }}
    QWidget#Content {{
        background: transparent;
    }}
    QFrame#Sidebar {{
        background: rgba(9, 14, 25, 0.72);
        border: none;
        border-right: 1px solid rgba(28, 42, 66, 0.7);
    }}
    QFrame#TitleBar {{
        background: transparent;
        border: none;
        border-bottom: 1px solid rgba(28, 42, 66, 0.55);
    }}
    QFrame#Card, QFrame#Panel {{
        background: rgba(15, 24, 41, 0.78);
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
        font-size: 26px;
        font-weight: 600;
    }}
    QLabel[role="h2"] {{
        color: {P.text};
        font-size: 17px;
        font-weight: 600;
    }}
    QLabel[role="muted"] {{
        color: {P.muted};
        font-size: 12px;
    }}
    QLabel[role="dim"] {{
        color: {P.dim};
        font-size: 11px;
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
        background: {P.panel_soft};
        border: 1px solid {P.border_soft};
        border-radius: 10px;
        padding: 8px 12px;
        color: {P.text};
        selection-background-color: rgba(34, 211, 238, 0.35);
        selection-color: {P.white};
    }}
    QLineEdit:hover {{
        border-color: {P.border};
    }}
    QLineEdit:focus {{
        border-color: rgba(34, 211, 238, 0.65);
        background: #0C1524;
    }}
    QLineEdit[mono="true"] {{
        font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
        font-size: 12px;
        letter-spacing: 0.5px;
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
        border-color: {P.border};
        color: {P.text};
    }}
    QPushButton:pressed {{
        background: #0B1322;
    }}
    QPushButton:disabled {{
        color: {P.dim};
        background: {P.panel_soft};
        border-color: {P.border_soft};
    }}
    QPushButton[variant="primary"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #22D3EE, stop:0.55 #4FC3F7, stop:1 #8B8CFF);
        color: #06121C;
        border: none;
        font-weight: 600;
        font-size: 13px;
        padding: 11px 20px;
    }}
    QPushButton[variant="primary"]:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3EE0F8, stop:0.55 #63CFFC, stop:1 #9C9DFF);
        color: #04101A;
    }}
    QPushButton[variant="primary"]:pressed {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1CBAD2, stop:0.55 #3FAEDB, stop:1 #7475E0);
    }}
    QPushButton[variant="primary"]:disabled {{
        background: {P.card};
        color: {P.dim};
    }}
    QPushButton[variant="danger"] {{
        background: rgba(255, 107, 122, 0.1);
        border: 1px solid rgba(255, 107, 122, 0.28);
        color: #FF9AA5;
    }}
    QPushButton[variant="danger"]:hover {{
        background: rgba(255, 107, 122, 0.17);
        border-color: rgba(255, 107, 122, 0.45);
    }}
    QPushButton[variant="ghost"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {P.muted};
        padding: 8px 12px;
    }}
    QPushButton[variant="ghost"]:hover {{
        background: rgba(255, 255, 255, 0.04);
        color: {P.text};
    }}
    QPushButton[variant="soft"] {{
        background: rgba(34, 211, 238, 0.08);
        border: 1px solid rgba(34, 211, 238, 0.2);
        color: #8CE8F7;
    }}
    QPushButton[variant="soft"]:hover {{
        background: rgba(34, 211, 238, 0.14);
        border-color: rgba(34, 211, 238, 0.35);
    }}
    QPushButton[variant="icon"] {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 9px;
        padding: 4px;
    }}
    QPushButton[variant="icon"]:hover {{
        background: rgba(255, 255, 255, 0.06);
    }}
    QPushButton[variant="window"] {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 0;
    }}
    QPushButton[variant="window"]:hover {{
        background: rgba(255, 255, 255, 0.07);
    }}
    QPushButton[variant="close"] {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 0;
    }}
    QPushButton[variant="close"]:hover {{
        background: rgba(255, 90, 105, 0.85);
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
        background: rgba(255, 255, 255, 0.045);
        color: {P.text_soft};
    }}
    QPushButton[chip="true"]:checked {{
        background: rgba(34, 211, 238, 0.1);
        border-color: rgba(34, 211, 238, 0.28);
        color: #7DE7F6;
    }}

    QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 9px;
        padding: 5px;
        color: {P.muted};
    }}
    QToolButton:hover {{
        background: rgba(255, 255, 255, 0.055);
        color: {P.text};
    }}

    QComboBox {{
        background: {P.panel_soft};
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
        background: {P.panel};
        border: 1px solid {P.border};
        border-radius: 10px;
        padding: 5px;
        selection-background-color: {P.selection};
        outline: none;
    }}

    QMenu {{
        background: #0E1626;
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
        background: rgba(34, 211, 238, 0.1);
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
        background: #101A2B;
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
        background: #25344B;
        border-radius: 3.5px;
        min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #334560;
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
        background: #25344B;
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
        background: #1A273D;
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #22D3EE, stop:1 #8B8CFF);
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: #EAF7FF;
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
        border: 2px solid #22D3EE;
    }}
    QSlider::handle:horizontal:hover {{
        background: #FFFFFF;
    }}

    QDialog {{
        background: #0B1320;
    }}
    QMessageBox {{
        background: #0B1320;
    }}
    QMessageBox QLabel {{
        color: {P.text_soft};
        font-size: 13px;
    }}
    QMessageBox QPushButton {{
        min-width: 92px;
    }}
    QToolBar {{
        background: transparent;
        border: none;
    }}
    QStatusBar {{
        background: transparent;
    }}
    """
