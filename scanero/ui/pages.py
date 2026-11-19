"""Application pages: scanner, favorites, history and settings."""
from __future__ import annotations

import time
from typing import Iterable

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics, QIntValidator
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.models import Device, Favorite, Service, kind_label
from ..core.netinfo import Interface, describe_targets, list_interfaces, parse_targets
from ..core.storage import HistoryEntry, Settings
from .icons import icon, pixmap
from .table import (
    COL_DEVICE,
    ROLE_DEVICE,
    DeviceFilterProxy,
    DeviceModel,
    DeviceTree,
    favorite_key,
)
from .theme import P, kind_color, rgba, service_color
from .widgets import (
    Avatar,
    EmptyState,
    FitStack,
    IconButton,
    NavButton,
    ProgressBar,
    RadarWidget,
    SearchField,
    ServiceChip,
    StatCard,
    StatusPill,
    ToggleSwitch,
    font,
    hline,
    plural,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _eyebrow(text: str) -> QLabel:
    label = QLabel(text.upper())
    f = font(9.6, QFont.Weight.DemiBold)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.4)
    label.setFont(f)
    label.setStyleSheet(f"color: {P.accent};")
    return label


def _title(text: str, size: int = 24) -> QLabel:
    label = QLabel(text)
    label.setFont(font(size, QFont.Weight.DemiBold))
    label.setStyleSheet(f"color: {P.text};")
    return label


def _muted(text: str, size: int = 12) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {P.muted}; font-size: {size}px;")
    label.setWordWrap(True)
    return label


def _section_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    f = font(9.4, QFont.Weight.DemiBold)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.1)
    label.setFont(f)
    label.setStyleSheet(f"color: {P.dim};")
    return label


def _page_header(title: str, subtitle: str, right: QWidget | None = None,
                 eyebrow: str = "Scanero") -> QWidget:
    widget = QWidget()
    row = QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(16)
    left = QVBoxLayout()
    left.setSpacing(3)
    left.addWidget(_eyebrow(eyebrow))
    left.addWidget(_title(title))
    left.addWidget(_muted(subtitle))
    row.addLayout(left, 1)
    if right is not None:
        row.addWidget(right, 0, Qt.AlignmentFlag.AlignBottom)
    return widget


def _setting_row(title: str, description: str, control: QWidget) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 11, 0, 11)
    layout.setSpacing(18)
    box = QVBoxLayout()
    box.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet(f"color: {P.text_soft}; font-size: 12.5px; font-weight: 500;")
    d = QLabel(description)
    d.setStyleSheet(f"color: {P.dim}; font-size: 11px;")
    d.setWordWrap(True)
    box.addWidget(t)
    box.addWidget(d)
    layout.addLayout(box, 1)
    layout.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


def _settings_card(title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 18, 20, 14)
    layout.setSpacing(2)
    head = QLabel(title)
    head.setFont(font(15, QFont.Weight.DemiBold))
    layout.addWidget(head)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setStyleSheet(f"color: {P.dim}; font-size: 11px;")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    layout.addSpacing(6)
    return card, layout


# ---------------------------------------------------------------------------
# Inspector
# ---------------------------------------------------------------------------

class InspectorPanel(QFrame):
    action_requested = pyqtSignal(str, object)
    service_requested = pyqtSignal(object, object)
    favorite_toggled = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFixedWidth(318)
        self.device: Device | None = None
        self._favorite = False
        self._iface: Interface | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        head = QHBoxLayout()
        head.addWidget(_section_label("Инспектор"))
        head.addStretch(1)
        self.star = IconButton("star", 17, P.dim, tooltip="Добавить в избранное")
        self.star.clicked.connect(self._toggle_favorite)
        head.addWidget(self.star)
        outer.addLayout(head)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        # --- empty state ----------------------------------------------------
        self.empty = QWidget()
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.setContentsMargins(0, 4, 0, 0)
        empty_layout.setSpacing(8)
        self.mini_radar = RadarWidget(150)
        empty_layout.addWidget(self.mini_radar, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addSpacing(8)
        empty_title = QLabel("Выберите устройство")
        empty_title.setFont(font(14, QFont.Weight.DemiBold))
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_hint = QLabel("Нажмите на строку в таблице, чтобы увидеть детали, сервисы и действия.")
        empty_hint.setStyleSheet(f"color: {P.muted}; font-size: 11.5px;")
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_hint.setWordWrap(True)
        empty_layout.addWidget(empty_hint)
        empty_layout.addSpacing(10)
        net_card = QFrame()
        net_card.setObjectName("NetCard")
        net_card.setStyleSheet(
            f"QFrame#NetCard {{ background:{P.input_bg}; border:1px solid {P.border_soft}; border-radius:12px; }}"
        )
        nc = QVBoxLayout(net_card)
        nc.setContentsMargins(14, 12, 14, 12)
        nc.setSpacing(3)
        nc.addWidget(_section_label("Ваша сеть"))
        self.empty_iface = QLabel("—")
        self.empty_iface.setStyleSheet(f"color:{P.text_soft}; font-size:12px; font-weight:500;")
        nc.addWidget(self.empty_iface)
        self.empty_ip = QLabel("")
        self.empty_ip.setStyleSheet(f"color:{P.muted}; font-size:11px; font-family:'JetBrains Mono';")
        nc.addWidget(self.empty_ip)
        self.empty_range = QLabel("")
        self.empty_range.setStyleSheet(f"color:{P.dim}; font-size:11px;")
        nc.addWidget(self.empty_range)
        self.net_card = net_card
        empty_layout.addWidget(net_card)
        empty_layout.addStretch(1)
        self.stack.addWidget(self.empty)

        # --- device view ----------------------------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.device_widget = QWidget()
        self.dv = QVBoxLayout(self.device_widget)
        self.dv.setContentsMargins(0, 0, 4, 0)
        self.dv.setSpacing(10)
        self.scroll.setWidget(self.device_widget)
        self.stack.addWidget(self.scroll)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.avatar = Avatar(56)
        top.addWidget(self.avatar)
        names = QVBoxLayout()
        names.setSpacing(2)
        self.name_label = QLabel("")
        self.name_label.setFont(font(15, QFont.Weight.DemiBold))
        self.name_label.setWordWrap(True)
        names.addWidget(self.name_label)
        self.ip_label = QLabel("")
        self.ip_label.setStyleSheet(
            f"color: {P.muted}; font-family:'JetBrains Mono'; font-size: 11.5px;"
        )
        names.addWidget(self.ip_label)
        self.pill = StatusPill()
        names.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignLeft)
        top.addLayout(names, 1)
        self.dv.addLayout(top)

        self.open_btn = QPushButton("Открыть")
        self.open_btn.setProperty("variant", "primary")
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_btn.setIcon(icon("arrow-up-right", P.primary_text, 17))
        self.open_btn.setIconSize(QSize(17, 17))
        self.open_btn.setFixedHeight(40)
        self.open_btn.setAutoDefault(False)
        self.open_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.open_btn.clicked.connect(lambda: self._emit_action("open_primary"))
        self.dv.addWidget(self.open_btn)

        self.dv.addSpacing(4)
        self.dv.addWidget(_section_label("Действия"))
        self.actions_grid = QGridLayout()
        self.actions_grid.setContentsMargins(0, 2, 0, 0)
        self.actions_grid.setSpacing(6)
        self.action_buttons: dict[str, QPushButton] = {}
        self.action_icon_colors: dict[str, str] = {}
        actions = [
            ("smb", "Файлы", "folder", P.amber, "Общие папки (SMB)"),
            ("http", "Веб", "globe", P.accent, "Веб-интерфейс"),
            ("rdp", "RDP", "monitor", P.pink, "Удалённый рабочий стол"),
            ("ssh", "SSH", "terminal", P.accent2, "Подключиться по SSH"),
            ("wol", "WOL", "power", P.green, "Wake-on-LAN"),
            ("ping", "Ping", "activity", P.green, "Проверить пинг"),
            ("copy", "Копировать", "copy", P.muted, "Скопировать сведения"),
            ("shutdown", "Выключить", "power", P.red, "Удалённое выключение"),
        ]
        for idx, (action, text, icon_name, color, tip) in enumerate(actions):
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tip)
            btn.setIcon(icon(icon_name, color, 15))
            btn.setIconSize(QSize(15, 15))
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda _=False, a=action: self._emit_action(a))
            self.actions_grid.addWidget(btn, idx // 2, idx % 2)
            self.action_buttons[action] = btn
            self.action_icon_colors[action] = color
        self.dv.addLayout(self.actions_grid)
        self.dv.addSpacing(4)

        services_head = QHBoxLayout()
        services_head.addWidget(_section_label("Сервисы"))
        self.services_count = QLabel("0")
        self.services_count.setStyleSheet(
            f"color:{P.accent}; background:{rgba(P.accent, 0.08)}; border-radius:6px; "
            "padding:1px 6px; font-size:10px; font-weight:600;"
        )
        services_head.addWidget(self.services_count)
        services_head.addStretch(1)
        self.dv.addLayout(services_head)
        self.services_box = QGridLayout()
        self.services_box.setContentsMargins(0, 0, 0, 0)
        self.services_box.setHorizontalSpacing(6)
        self.services_box.setVerticalSpacing(6)
        self.dv.addLayout(self.services_box)
        self.no_services = _muted("Открытые сервисы не обнаружены", 11)
        self.no_services.setVisible(False)
        self.dv.addWidget(self.no_services)

        self.dv.addSpacing(4)
        self.dv.addWidget(_section_label("Сведения"))
        self.info_grid = QGridLayout()
        self.info_grid.setContentsMargins(0, 2, 0, 0)
        self.info_grid.setHorizontalSpacing(10)
        self.info_grid.setVerticalSpacing(7)
        self.info_values: dict[str, QLabel] = {}
        rows = [
            ("MAC", "mac"), ("Производитель", "vendor"), ("NetBIOS", "netbios"),
            ("Рабочая группа", "workgroup"), ("ОС", "os"), ("TTL", "ttl"), ("Тип", "kind"),
        ]
        for idx, (label, key) in enumerate(rows):
            lab = QLabel(label)
            lab.setStyleSheet(f"color:{P.dim}; font-size:11px;")
            val = QLabel("—")
            val.setStyleSheet(f"color:{P.text_soft}; font-size:11.5px;")
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.info_grid.addWidget(lab, idx, 0, Qt.AlignmentFlag.AlignTop)
            self.info_grid.addWidget(val, idx, 1, Qt.AlignmentFlag.AlignTop)
            self.info_grid.setColumnStretch(1, 1)
            self.info_values[key] = val
        self.dv.addLayout(self.info_grid)
        self.dv.addStretch(1)
        self.stack.setCurrentIndex(0)

    def refresh_theme(self) -> None:
        self.star.setIcon(icon(
            "star-fill" if self._favorite else "star",
            P.amber if self._favorite else P.dim, 17,
        ))
        self.open_btn.setIcon(icon("arrow-up-right", P.primary_text, 17))
        self.net_card.setStyleSheet(
            f"QFrame#NetCard {{ background:{P.input_bg}; border:1px solid {P.border_soft}; border-radius:12px; }}"
        )
        for action, color in self.action_icon_colors.items():
            button = self.action_buttons[action]
            old = button.icon()
            name = {
                "smb": "folder", "http": "globe", "rdp": "monitor", "ssh": "terminal",
                "wol": "power", "ping": "activity", "copy": "copy", "shutdown": "power",
            }.get(action, "signal")
            button.setIcon(icon(name, color, 15))
        if self.device is not None:
            self.pill.set_status(self.device.status)
        for label in self.info_values.values():
            label.setStyleSheet(f"color:{P.text_soft}; font-size:11.5px;")
        self.avatar.update()
        self.mini_radar.update()

    def _emit_action(self, action: str) -> None:
        if self.device is not None:
            self.action_requested.emit(action, self.device)

    def _toggle_favorite(self) -> None:
        if self.device is not None:
            self.favorite_toggled.emit(self.device)

    def set_favorite(self, value: bool) -> None:
        self._favorite = value
        self.star.setIcon(icon("star-fill" if value else "star", P.amber if value else P.dim, 17))
        self.star.setToolTip("Удалить из избранного" if value else "Добавить в избранное")

    def set_interface(self, iface: Interface | None) -> None:
        self._iface = iface
        if iface:
            self.empty_iface.setText(iface.title)
            self.empty_ip.setText(f"{iface.ip}/{iface.prefix}")
            self.empty_range.setText(f"Диапазон: {iface.default_range}")
        else:
            self.empty_iface.setText("Нет активного подключения")
            self.empty_ip.setText("")
            self.empty_range.setText("")

    def clear(self) -> None:
        self.device = None
        self.stack.setCurrentIndex(0)
        self.star.setVisible(False)
        self.mini_radar.set_devices([])

    def update_device(self, device: Device, favorite: bool | None = None) -> None:
        if device is None:
            self.clear()
            return
        self.device = device
        self.stack.setCurrentIndex(1)
        self.star.setVisible(True)
        self.avatar.set_device(device)
        self.name_label.setText(device.title or "Без имени")
        self.ip_label.setText(device.ip)
        self.pill.set_status(device.status)
        self.set_favorite(favorite if favorite is not None else device.favorite)

        values = {
            "mac": device.mac or "—",
            "vendor": device.vendor or "—",
            "netbios": device.netbios or "—",
            "workgroup": device.workgroup or "—",
            "os": device.os_name or "—",
            "ttl": str(device.ttl) if device.ttl else "—",
            "kind": kind_label(device.kind),
        }
        for key, label in self.info_values.items():
            label.setText(values.get(key, "—"))

        # services
        while self.services_box.count():
            item = self.services_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for idx, service in enumerate(sorted(device.services, key=lambda s: s.port)):
            chip = ServiceChip(service)
            chip.clicked_service.connect(lambda d=device, s=service: self.service_requested.emit(d, s))
            self.services_box.addWidget(chip, idx // 2, idx % 2)
        self.services_count.setText(str(len(device.services)))
        self.no_services.setVisible(not device.services)

        kinds = device.service_kinds
        self.open_btn.setEnabled(device.is_online() and bool(device.services))
        self.open_btn.setToolTip(
            f"Открыть {device.primary_service.name}" if device.primary_service else "Нет доступных ресурсов"
        )
        self.action_buttons["smb"].setEnabled(device.is_online() and bool(kinds & {"smb", "netbios", "ftp", "afp"}))
        self.action_buttons["http"].setEnabled(device.is_online() and bool(kinds & {"http", "https"}))
        self.action_buttons["rdp"].setEnabled(device.is_online() and "rdp" in kinds)
        self.action_buttons["ssh"].setEnabled(device.is_online() and "ssh" in kinds)
        self.action_buttons["wol"].setEnabled(bool(device.mac))
        self.action_buttons["ping"].setEnabled(device.is_online())
        self.action_buttons["copy"].setEnabled(True)
        self.action_buttons["shutdown"].setEnabled(device.is_online())
        QTimer.singleShot(0, self._sync_content_height)

    def _sync_content_height(self) -> None:
        self.dv.activate()
        self.device_widget.setMinimumHeight(self.device_widget.sizeHint().height())


# ---------------------------------------------------------------------------
# Scanner page
# ---------------------------------------------------------------------------

class ScannerPage(QWidget):
    scan_requested = pyqtSignal(str)
    stop_requested = pyqtSignal()
    action_requested = pyqtSignal(str, object)
    service_requested = pyqtSignal(object, object)
    favorite_toggled = pyqtSignal(object)
    export_requested = pyqtSignal(str)
    settings_requested = pyqtSignal()
    range_changed = pyqtSignal(str)
    filter_changed = pyqtSignal(str)

    def __init__(self, settings: Settings, favorites: list[Favorite], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.favorite_items = favorites
        self._iface: Interface | None = None
        self._interfaces: list[Interface] = []
        self._scanning = False
        self._last_result = None
        self._current: Device | None = None
        self._radar_devices: list[Device] = []

        self.model = DeviceModel(self)
        self.proxy = DeviceFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.tree = DeviceTree()
        self.tree.set_model(self.proxy)
        self.tree.device_selected.connect(self._on_selected)
        self.tree.device_activated.connect(self._on_activated)
        self.tree.service_activated.connect(self.service_requested.emit)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 14)
        root.setSpacing(14)

        root.addWidget(_page_header(
            "Все устройства в вашей сети",
            "Быстрое сканирование, MAC-адреса, имена и открытые сервисы.",
            eyebrow="Сканирование",
        ))

        # control panel
        self.control = QFrame()
        self.control.setObjectName("Panel")
        cp = QHBoxLayout(self.control)
        cp.setContentsMargins(12, 10, 10, 10)
        cp.setSpacing(10)
        target_tile = QLabel()
        self.target_tile = target_tile
        target_tile.setFixedSize(38, 38)
        target_tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        target_tile.setPixmap(pixmap("target", P.accent, 20))
        target_tile.setStyleSheet(
            f"background: {rgba(P.accent, 0.08)}; border:1px solid {rgba(P.accent, 0.18)}; border-radius:10px;"
        )
        cp.addWidget(target_tile)
        self.range_edit = QLineEdit()
        self.range_edit.setProperty("mono", "true")
        self.range_edit.setMinimumHeight(42)
        self.range_edit.setPlaceholderText("192.168.1.0/24 или 192.168.1.10-192.168.1.100")
        self.range_edit.returnPressed.connect(self._request_scan)
        self.range_edit.textEdited.connect(self.range_changed.emit)
        self.range_edit.textChanged.connect(lambda _: self._update_idle_text())
        cp.addWidget(self.range_edit, 1)
        self.network_btn = QPushButton("Моя сеть")
        self.network_btn.setIcon(icon("wifi", P.muted, 16))
        self.network_btn.setIconSize(QSize(16, 16))
        self.network_btn.setFixedHeight(42)
        self.network_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.network_btn.setToolTip("Подставить диапазон текущей сети")
        self.network_btn.clicked.connect(self._show_network_menu)
        cp.addWidget(self.network_btn)
        self.scan_btn = QPushButton("Сканировать")
        self.scan_btn.setProperty("variant", "primary")
        self.scan_btn.setIcon(icon("scan", P.primary_text, 17))
        self.scan_btn.setIconSize(QSize(17, 17))
        self.scan_btn.setFixedHeight(42)
        self.scan_btn.setMinimumWidth(166)
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.clicked.connect(self._scan_clicked)
        cp.addWidget(self.scan_btn)
        root.addWidget(self.control)

        self.progress = ProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        # stats
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.stat_online = StatCard("В сети", "radio", P.green)
        self.stat_services = StatCard("Сервисы", "signal", P.accent2)
        self.stat_offline = StatCard("Не в сети", "power", P.red)
        self.stat_time = StatCard("Время", "history", P.accent)
        for card in (self.stat_online, self.stat_services, self.stat_offline, self.stat_time):
            stats.addWidget(card, 1)
        root.addLayout(stats)

        # filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        self.chips: dict[str, QPushButton] = {}
        for mode, label in (
            ("online", "В сети"),
            ("all", "Все адреса"),
            ("services", "С сервисами"),
            ("favorites", "Избранное"),
        ):
            chip = QPushButton(label)
            chip.setProperty("chip", "true")
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, m=mode: self.set_filter(m))
            self.chip_group.addButton(chip)
            self.chips[mode] = chip
            filter_row.addWidget(chip)
        filter_row.addStretch(1)
        self.search = SearchField("Поиск по имени, IP, MAC…")
        self.search.setFixedWidth(262)
        self.search.setMinimumHeight(36)
        self.search.textChanged.connect(self._on_search)
        filter_row.addWidget(self.search)
        self.inspector_btn = QPushButton("Детали")
        self.inspector_btn.setProperty("chip", "true")
        self.inspector_btn.setCheckable(True)
        self.inspector_btn.setChecked(True)
        self.inspector_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.inspector_btn.setToolTip("Показать или скрыть панель сведений")
        self.inspector_btn.toggled.connect(lambda checked: self.inspector.setVisible(checked))
        filter_row.addWidget(self.inspector_btn)
        self.export_btn = QPushButton()
        self.export_btn.setProperty("variant", "icon")
        self.export_btn.setIcon(icon("download", P.muted, 17))
        self.export_btn.setIconSize(QSize(17, 17))
        self.export_btn.setFixedSize(38, 36)
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setToolTip("Сохранить отчёт")
        self.export_menu = QMenu(self)
        for fmt, label in (("csv", "CSV (Excel)"), ("json", "JSON"), ("html", "HTML-отчёт")):
            act = self.export_menu.addAction(icon("download", P.muted, 14), label)
            act.triggered.connect(lambda _=False, f=fmt: self.export_requested.emit(f))
        self.export_btn.clicked.connect(self._show_export_menu)
        filter_row.addWidget(self.export_btn)
        root.addLayout(filter_row)

        # table + inspector
        body = QHBoxLayout()
        body.setSpacing(14)
        self.table_card = QFrame()
        self.table_card.setObjectName("Card")
        table_layout = QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        self.stack = FitStack()
        self.empty = EmptyState()
        self.empty.scan_clicked.connect(self._empty_scan_clicked)
        self.empty.reset_clicked.connect(self._reset_filters)
        self.empty.settings_clicked.connect(self._focus_range)
        self.stack.addWidget(self.empty)
        tree_wrap = QWidget()
        tw = QVBoxLayout(tree_wrap)
        tw.setContentsMargins(0, 2, 0, 6)
        tw.addWidget(self.tree)
        self.stack.addWidget(tree_wrap)
        table_layout.addWidget(self.stack)
        body.addWidget(self.table_card, 1)
        self.inspector = InspectorPanel()
        self.inspector.action_requested.connect(self.action_requested.emit)
        self.inspector.service_requested.connect(self.service_requested.emit)
        self.inspector.favorite_toggled.connect(self.favorite_toggled.emit)
        body.addWidget(self.inspector)
        root.addLayout(body, 1)

        # footer
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.status_dot = QLabel()
        self.status_dot.setPixmap(pixmap("radio", P.green, 13))
        footer.addWidget(self.status_dot)
        self.status_label = QLabel("Готово к работе")
        self.status_label.setStyleSheet(f"color:{P.muted}; font-size:11px;")
        footer.addWidget(self.status_label)
        footer.addStretch(1)
        self.footer_info = QLabel("")
        self.footer_info.setStyleSheet(f"color:{P.dim}; font-size:11px;")
        footer.addWidget(self.footer_info)
        root.addLayout(footer)

        self._select_filter(self.settings.get("filter", "online"), emit=False)
        self.set_interface(None, list_interfaces())
        self._update_counts()
        self.update_stats(0, 0, 0, "—")

    # -- external API --------------------------------------------------------
    def set_interface(self, iface: Interface | None, interfaces: list[Interface] | None = None) -> None:
        old_default = self._iface.default_range if self._iface else ""
        self._iface = iface
        if interfaces is not None:
            self._interfaces = interfaces
        if iface:
            current = self.range_edit.text().strip()
            if not current or current == old_default:
                self.range_edit.setText(iface.default_range)
            self.empty.show_idle(0, iface.default_range)
            self.inspector.set_interface(iface)
            self._update_idle_text()
        else:
            self.inspector.set_interface(None)

    def set_favorites(self, favorites: list[Favorite]) -> None:
        self.favorite_items = favorites
        keys = {f.key for f in favorites} | {f.ip for f in favorites}
        self.model.set_favorite_flags(keys)
        self.proxy.set_favorites(keys)
        if self._current:
            self.inspector.set_favorite(self._current.favorite)
        self._update_counts()
        self._update_empty_state()

    def set_scanning(self, running: bool) -> None:
        self._scanning = running
        self.scan_btn.setText("Остановить" if running else "Сканировать")
        self.scan_btn.setIcon(icon("stop" if running else "scan", P.primary_text, 15 if running else 17))
        self.range_edit.setEnabled(not running)
        self.network_btn.setEnabled(not running)
        self.progress.setVisible(running)
        if running:
            self.progress.set_value(0, animate=False)
            self.status_label.setText("Сканирование сети…")
            self.status_dot.setPixmap(pixmap("radio", P.accent, 13))
            self.empty.show_scanning()
            self.empty.set_devices([])
            self.stack.setCurrentIndex(0)
        else:
            self.status_dot.setPixmap(pixmap("radio", P.green, 13))

    def reset_results(self) -> None:
        self.model.clear_devices()
        self._current = None
        self._radar_devices = []
        self.inspector.clear()
        self.empty.set_devices([])
        self.update_stats(0, 0, 0, "—")
        self._update_counts()
        self._update_empty_state()

    def on_found(self, device: Device) -> None:
        device.favorite = self._is_favorite(device)
        self.model.add_or_update(device)
        if self._current and self._current.ip == device.ip:
            self._current = device
            self.inspector.update_device(device, device.favorite)
        self._radar_devices.append(device)
        self.empty.set_devices(self._radar_devices)
        self.inspector.mini_radar.set_devices(self._radar_devices)
        self.tree.viewport().update()
        self._update_counts()
        if device.is_online():
            n = self.model.rowCount()
            self.stat_online.set_value(self.model.online_count(), f"из {n} {plural(n, 'адреса', 'адресов', 'адресов')}")
        if self._scanning and self.model.online_count() > 0:
            self.stack.setCurrentIndex(1)

    def on_updated(self, device: Device) -> None:
        device.favorite = self._is_favorite(device)
        self.model.add_or_update(device)
        if device.is_online():
            self._radar_devices = [d for d in self._radar_devices if d.ip != device.ip]
            self._radar_devices.append(device)
            self.empty.set_devices(self._radar_devices)
        if self._current and self._current.ip == device.ip:
            self._current = device
            self.inspector.update_device(device)
        self._update_counts()
        self.stat_services.set_value(self.model.services_count(), "открытых портов")
        self.tree.viewport().update()

    def on_progress(self, payload: dict) -> None:
        total = max(1, int(payload.get("total", 1)))
        done = int(payload.get("done", 0))
        if payload.get("stage") == "discover":
            percent = min(100, done / total * 55)
            stage = "Поиск устройств"
        else:
            percent = 55 + min(100, done / max(1, int(payload.get("total", 1))) * 45)
            stage = "Определение сервисов"
        self.progress.set_value(percent)
        self.status_label.setText(f"{stage} · {done} из {total}")
        if self.model.online_count() == 0:
            self.empty.set_progress(percent, f"{stage}: {done} из {total}")
        self.footer_info.setText(f"Найдено: {self.model.online_count()}")
        self._update_counts()

    def on_result(self, result) -> None:
        self._last_result = result
        for device in result.devices:
            device.favorite = self._is_favorite(device)
            self.model.add_or_update(device)
            if self._current and self._current.ip == device.ip:
                self._current = device
                self.inspector.update_device(device, device.favorite)
        self._radar_devices = [d for d in result.devices if d.is_online()]
        self.empty.set_devices(self._radar_devices)
        self.update_stats(result.online, result.services, result.offline, f"{result.duration:.1f} с")
        self.stat_online.set_value(
            result.online,
            f"из {result.target_count} {plural(result.target_count, 'адреса', 'адресов', 'адресов')}",
            animate=True,
        )
        self.stat_offline.set_value(result.offline, "не отвечают", animate=True)
        self.set_scanning(False)
        self.progress.setVisible(False)
        if result.cancelled:
            self.status_label.setText("Сканирование остановлено")
        else:
            self.status_label.setText(
                f"Сканирование завершено · {result.online} "
                f"{plural(result.online, 'устройство', 'устройства', 'устройств')} · "
                f"{result.services} {plural(result.services, 'сервис', 'сервиса', 'сервисов')}"
            )
        self.footer_info.setText(
            f"{result.online} в сети · {result.services} "
            f"{plural(result.services, 'сервис', 'сервиса', 'сервисов')} · {result.duration:.1f} с"
        )
        self._update_counts()
        self._update_empty_state()
        if self.model.online_count() > 0:
            self.stack.setCurrentIndex(1)

    def load_snapshot(self, entry: HistoryEntry) -> None:
        self._select_filter("online", emit=False)
        self.model.clear_devices()
        self._current = None
        self.inspector.clear()
        self.range_edit.setText(entry.range_expr)
        devices = entry.device_objects()
        for device in devices:
            device.favorite = self._is_favorite(device)
            self.model.add_or_update(device)
        self._radar_devices = [d for d in devices if d.is_online()]
        self.empty.set_devices(self._radar_devices)
        self.update_stats(entry.online, entry.services, entry.offline, f"{entry.duration:.1f} с")
        self.status_label.setText(f"Снимок от {entry.date_label}")
        self.footer_info.setText(f"{entry.online} в сети · {entry.services} сервисов")
        self._update_counts()
        self._update_empty_state()
        if devices:
            self.stack.setCurrentIndex(1)

    def update_stats(self, online: int, services: int, offline: int, duration: str) -> None:
        self.stat_online.set_value(online, "устройств онлайн")
        self.stat_services.set_value(services, "открытых портов")
        self.stat_offline.set_value(offline, "не отвечают")
        self.stat_time.set_value(duration, "длительность")

    def set_filter(self, mode: str) -> None:
        self._select_filter(mode, emit=True)

    def _select_filter(self, mode: str, emit: bool) -> None:
        if mode not in self.chips:
            mode = "online"
        self.chips[mode].setChecked(True)
        self.proxy.set_mode(mode)
        if emit:
            self.filter_changed.emit(mode)
        self._update_empty_state()

    def _reset_filters(self) -> None:
        self.search.clear()
        self._select_filter("online", emit=True)

    def _on_search(self, text: str) -> None:
        self.proxy.set_search(text)
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        if self._scanning:
            self.stack.setCurrentIndex(0 if self.model.online_count() == 0 else 1)
            return
        total = self.model.rowCount()
        visible = self.proxy.rowCount()
        if total == 0:
            count, range_text = 0, ""
            try:
                if self._iface:
                    count = len(parse_targets(self.range_edit.text() or self._iface.default_range, self._interfaces))
                range_text = self.range_edit.text() or (self._iface.default_range if self._iface else "")
            except Exception:
                range_text = self.range_edit.text()
            self.empty.show_idle(count, range_text)
            self.stack.setCurrentIndex(0)
        elif visible == 0:
            self.empty.show_no_results(bool(self.search.text().strip()) or self.proxy._mode != "online")
            self.stack.setCurrentIndex(0)
        else:
            self.stack.setCurrentIndex(1)

    def _update_idle_text(self) -> None:
        if self.model.rowCount() > 0 or self._scanning:
            return
        text = self.range_edit.text().strip() or (self._iface.default_range if self._iface else "")
        count = 0
        try:
            count = len(parse_targets(text, self._interfaces))
        except Exception:
            pass
        self.empty.show_idle(count, text)

    def _update_counts(self) -> None:
        online = self.model.online_count()
        total = self.model.rowCount()
        services = self.model.with_services_count()
        favs = len(self.favorite_items)
        labels = {
            "online": f"В сети · {online}",
            "all": f"Все адреса · {total}",
            "services": f"С сервисами · {services}",
            "favorites": f"Избранное · {favs}",
        }
        for mode, label in labels.items():
            self.chips[mode].setText(label)
        if not self._scanning and self.model.rowCount() == 0:
            self.footer_info.setText("")
        self._update_idle_text()

    def refresh_theme(self) -> None:
        self.target_tile.setPixmap(pixmap("target", P.accent, 20))
        self.target_tile.setStyleSheet(
            f"background: {rgba(P.accent, 0.08)}; border:1px solid {rgba(P.accent, 0.18)}; border-radius:10px;"
        )
        self.network_btn.setIcon(icon("wifi", P.muted, 16))
        self.export_btn.setIcon(icon("download", P.muted, 17))
        self.scan_btn.setIcon(
            icon("stop" if self._scanning else "scan", P.primary_text, 15 if self._scanning else 17)
        )
        self.stat_online.set_color(P.green)
        self.stat_services.set_color(P.accent2)
        self.stat_offline.set_color(P.red)
        self.stat_time.set_color(P.accent)
        self.empty.refresh_theme()
        self.inspector.refresh_theme()
        self.tree.viewport().update()
        self.update()

    def update_favorite(self, device: Device, favorite: bool) -> None:
        device.favorite = favorite
        keys = {f.key for f in self.favorite_items} | {f.ip for f in self.favorite_items}
        self.proxy.set_favorites(keys)
        if self._current and self._current.ip == device.ip:
            self.inspector.set_favorite(favorite)
        self._update_counts()

    def _is_favorite(self, device: Device) -> bool:
        return any(f.matches(device) for f in self.favorite_items)

    def _scan_clicked(self) -> None:
        if self._scanning:
            self.stop_requested.emit()
        else:
            self._request_scan()

    def _request_scan(self) -> None:
        self.scan_requested.emit(self.range_edit.text().strip())

    def _focus_range(self) -> None:
        self.range_edit.setFocus()
        self.range_edit.selectAll()

    def _empty_scan_clicked(self) -> None:
        if self._scanning:
            self.stop_requested.emit()
        else:
            self._request_scan()

    def _show_export_menu(self) -> None:
        self.export_menu.exec(
            self.export_btn.mapToGlobal(self.export_btn.rect().bottomLeft())
        )

    def _show_network_menu(self) -> None:
        menu = QMenu(self)
        if not self._interfaces:
            act = menu.addAction("Интерфейсы не найдены")
            act.setEnabled(False)
        for iface in self._interfaces:
            title = f"{iface.title} · {iface.ssid}" if iface.ssid else iface.title
            act = menu.addAction(icon("wifi" if iface.wireless else "ethernet", P.muted, 15), title)
            act.triggered.connect(lambda _=False, r=iface.default_range: self._set_range(r))
            subnet = iface.whole_subnet
            if subnet != iface.default_range:
                act2 = menu.addAction(f"    вся подсеть {subnet}")
                act2.triggered.connect(lambda _=False, r=subnet: self._set_range(r))
        menu.addSeparator()
        act_c = menu.addAction(icon("target", P.muted, 15), "Подсеть класса C из текущего адреса")
        act_c.triggered.connect(self._set_class_c)
        act = menu.addAction(icon("settings", P.muted, 15), "Настройки сканирования")
        act.triggered.connect(self.settings_requested.emit)
        menu.exec(self.network_btn.mapToGlobal(self.network_btn.rect().bottomLeft()))

    def _set_range(self, text: str) -> None:
        self.range_edit.setText(text)
        self.range_changed.emit(text)
        self._update_idle_text()

    def _set_class_c(self) -> None:
        text = self.range_edit.text().strip()
        try:
            first = text.split("-")[0].split("/")[0]
            octets = first.split(".")[:3]
            self._set_range(".".join(octets) + ".0/24")
        except Exception:
            pass

    def _on_selected(self, device: Device | None) -> None:
        if device is None:
            self.inspector.clear()
            self._current = None
            return
        self._current = device
        self.inspector.update_device(device, self._is_favorite(device))

    def _on_activated(self, device: Device) -> None:
        self.action_requested.emit("open_primary", device)

    def _context_menu(self, pos) -> None:
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        top = index.parent() if index.parent().isValid() else index
        device = top.data(ROLE_DEVICE)
        if not isinstance(device, Device):
            return
        if not self.tree.selectionModel().isSelected(index):
            self.tree.setCurrentIndex(top)
        menu = QMenu(self)
        if device.services:
            act = menu.addAction(icon("arrow-up-right", P.accent, 15), "Открыть")
            act.triggered.connect(lambda: self.action_requested.emit("open_primary", device))
        fav = self._is_favorite(device)
        act = menu.addAction(icon("star-fill" if fav else "star", P.amber if fav else P.muted, 15),
                             "Удалить из избранного" if fav else "Добавить в избранное")
        act.triggered.connect(lambda: self.favorite_toggled.emit(device))
        menu.addSeparator()
        for action, label, icon_name, enabled in (
            ("smb", "Общие папки", "folder", bool(device.service_kinds & {"smb", "netbios", "ftp", "afp"})),
            ("http", "Веб-интерфейс", "globe", bool(device.service_kinds & {"http", "https"})),
            ("rdp", "RDP", "monitor", "rdp" in device.service_kinds),
            ("ssh", "SSH", "terminal", "ssh" in device.service_kinds),
            ("wol", "Wake-on-LAN", "power", bool(device.mac)),
        ):
            act = menu.addAction(icon(icon_name, P.muted, 15), label)
            act.setEnabled(enabled and device.is_online() or action == "wol" and bool(device.mac))
            act.triggered.connect(lambda _=False, a=action, d=device: self.action_requested.emit(a, d))
        menu.addSeparator()
        act = menu.addAction(icon("radar", P.accent, 15), "Сканировать этот адрес")
        act.triggered.connect(lambda: self.scan_requested.emit(device.ip))
        menu.addSeparator()
        for action, label, icon_name in (
            ("ping", "Ping", "activity"),
            ("trace", "Traceroute", "network"),
            ("copy", "Копировать сведения", "copy"),
            ("shutdown", "Выключить…", "power"),
        ):
            act = menu.addAction(icon(icon_name, P.muted, 15), label)
            act.triggered.connect(lambda _=False, a=action, d=device: self.action_requested.emit(a, d))
        menu.exec(self.tree.viewport().mapToGlobal(pos))


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------

class FavoriteCard(QFrame):
    scan_clicked = pyqtSignal(object)
    remove_clicked = pyqtSignal(object)

    def __init__(self, favorite: Favorite, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.favorite = favorite
        self.setObjectName("FavoriteCard")
        self.setStyleSheet(
            f"QFrame#FavoriteCard {{ background: {rgba(P.card, 0.92)};"
            f" border:1px solid {P.border_soft}; border-radius:14px; }}"
            f"QFrame#FavoriteCard:hover {{ border-color:{P.border_hover};"
            f" background:{P.card_hover}; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 13, 14, 13)
        layout.setSpacing(13)
        self.avatar = Avatar(44)
        fake = Device(
            ip=favorite.ip, name=favorite.name, mac=favorite.mac,
            vendor=favorite.vendor, status="unknown", kind=favorite.kind or "unknown",
            os_name=favorite.os_name,
        )
        self.avatar.set_device(fake)
        layout.addWidget(self.avatar)
        box = QVBoxLayout()
        box.setSpacing(2)
        name = QLabel(favorite.name or "Без имени")
        name.setFont(font(13, QFont.Weight.DemiBold))
        box.addWidget(name)
        meta = QLabel(f"{favorite.ip}    {favorite.mac or 'MAC неизвестен'}")
        meta.setStyleSheet(f"color:{P.muted}; font-family:'JetBrains Mono'; font-size:10.5px;")
        box.addWidget(meta)
        subline = favorite.vendor or (favorite.note or "")
        if favorite.note and favorite.vendor:
            subline = f"{favorite.vendor} · {favorite.note}"
        sub = QLabel(subline or "Сохранённое устройство")
        sub.setStyleSheet(f"color:{P.dim}; font-size:10.8px;")
        box.addWidget(sub)
        layout.addLayout(box, 1)
        last = QLabel(
            time.strftime("%d.%m.%Y", time.localtime(favorite.last_seen or favorite.added))
            if (favorite.last_seen or favorite.added) else "—"
        )
        last.setStyleSheet(f"color:{P.dim}; font-size:10.5px;")
        layout.addWidget(last)
        scan = QPushButton("Сканировать")
        scan.setProperty("variant", "soft")
        scan.setIcon(icon("play", P.accent_soft, 14))
        scan.setIconSize(QSize(14, 14))
        scan.setFixedHeight(32)
        scan.setCursor(Qt.CursorShape.PointingHandCursor)
        scan.clicked.connect(lambda: self.scan_clicked.emit(self.favorite))
        layout.addWidget(scan)
        remove = IconButton("trash", 15, P.dim, tooltip="Удалить из избранного")
        remove.clicked.connect(lambda: self.remove_clicked.emit(self.favorite))
        layout.addWidget(remove)


class FavoritesPage(QWidget):
    scan_single = pyqtSignal(str)
    scan_all = pyqtSignal(str)
    remove_requested = pyqtSignal(object)
    about_requested = pyqtSignal()

    def __init__(self, favorites: list[Favorite], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.favorites = favorites
        self._cards: list[FavoriteCard] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 18)
        root.setSpacing(16)
        self.subtitle = "Устройства, к которым вы хотите возвращаться."
        self.header = _page_header("Избранное", self.subtitle, eyebrow="Коллекция")
        root.addWidget(self.header)

        action_row = QHBoxLayout()
        self.count_label = QLabel("0 устройств")
        self.count_label.setStyleSheet(f"color:{P.muted}; font-size:12px;")
        action_row.addWidget(self.count_label)
        action_row.addStretch(1)
        self.scan_all_btn = QPushButton("Сканировать избранное")
        self.scan_all_btn.setProperty("variant", "primary")
        self.scan_all_btn.setIcon(icon("radar", P.primary_text, 16))
        self.scan_all_btn.setIconSize(QSize(16, 16))
        self.scan_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_all_btn.clicked.connect(self._scan_all)
        action_row.addWidget(self.scan_all_btn)
        root.addLayout(action_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(8)
        self.empty = QWidget()
        ev = QVBoxLayout(self.empty)
        ev.setContentsMargins(0, 60, 0, 0)
        ev.setSpacing(8)
        star_icon = QLabel()
        self.empty_icon = star_icon
        star_icon.setPixmap(icon("star", P.amber, 46).pixmap(46, 46))
        star_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(star_icon)
        et = QLabel("Пока нет избранных устройств")
        et.setFont(font(17, QFont.Weight.DemiBold))
        et.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(et)
        ed = _muted("Добавьте устройства из результатов сканирования — они всегда будут под рукой.", 12)
        ed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(ed)
        self.list_layout.addWidget(self.empty)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)
        self.refresh(favorites)

    def refresh(self, favorites: list[Favorite]) -> None:
        self.favorites = favorites
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        for fav in sorted(favorites, key=lambda f: (f.name or f.ip).lower()):
            card = FavoriteCard(fav)
            card.scan_clicked.connect(lambda f: self.scan_single.emit(f.ip))
            card.remove_clicked.connect(self.remove_requested.emit)
            self._cards.append(card)
            self.list_layout.insertWidget(self.list_layout.count() - 2, card)
        self.empty.setVisible(not favorites)
        n = len(favorites)
        self.count_label.setText(
            f"{n} {plural(n, 'устройство', 'устройства', 'устройств')}" if n else "Нет устройств"
        )
        self.scan_all_btn.setEnabled(bool(favorites))

    def refresh_theme(self) -> None:
        self.empty_icon.setPixmap(icon("star", P.amber, 46).pixmap(46, 46))
        self.refresh(self.favorites)

    def _scan_all(self) -> None:
        if self.favorites:
            self.scan_all.emit(", ".join(f.ip for f in self.favorites if f.ip))


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class HistoryCard(QFrame):
    open_clicked = pyqtSignal(object)
    repeat_clicked = pyqtSignal(object)

    def __init__(self, entry: HistoryEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("HistoryCard")
        self.setStyleSheet(
            f"QFrame#HistoryCard {{ background: {rgba(P.card, 0.92)}; border:1px solid {P.border_soft};"
            f" border-radius:14px; }} QFrame#HistoryCard:hover {{ border-color:{P.border_hover}; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 14, 12)
        layout.setSpacing(14)
        icon_label = QLabel()
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            f"background: {rgba(P.accent, 0.07)}; border:1px solid {rgba(P.accent, 0.15)}; border-radius:10px;"
        )
        icon_label.setPixmap(pixmap("history", P.accent, 19))
        layout.addWidget(icon_label)
        box = QVBoxLayout()
        box.setSpacing(2)
        when = QLabel(entry.date_label)
        when.setFont(font(12.5, QFont.Weight.DemiBold))
        box.addWidget(when)
        rng = QLabel(entry.range_expr or "—")
        rng.setStyleSheet(f"color:{P.muted}; font-family:'JetBrains Mono'; font-size:10.5px;")
        box.addWidget(rng)
        layout.addLayout(box, 1)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for text, color in (
            (f"{entry.online} в сети", P.green),
            (f"{entry.services} {plural(entry.services, 'сервис', 'сервиса', 'сервисов')}", P.accent2),
            (f"{entry.duration:.1f} с", P.muted),
        ):
            chip = QLabel(text)
            chip.setStyleSheet(
                f"color:{color}; background: {rgba(P.hover_rgb, 0.035)}; border:1px solid {P.border};"
                "border-radius:7px; padding:3px 8px; font-size:10.5px;"
            )
            chips.addWidget(chip)
        layout.addLayout(chips)
        open_btn = QPushButton("Открыть")
        open_btn.setProperty("variant", "soft")
        open_btn.setFixedHeight(32)
        open_btn.setIcon(icon("eye", P.accent_soft, 14))
        open_btn.setIconSize(QSize(14, 14))
        open_btn.clicked.connect(lambda: self.open_clicked.emit(self.entry))
        layout.addWidget(open_btn)
        repeat = QPushButton("Повторить")
        repeat.setFixedHeight(32)
        repeat.setIcon(icon("refresh", P.muted, 14))
        repeat.setIconSize(QSize(14, 14))
        repeat.clicked.connect(lambda: self.repeat_clicked.emit(self.entry))
        layout.addWidget(repeat)


class HistoryPage(QWidget):
    open_entry = pyqtSignal(object)
    repeat_entry = pyqtSignal(object)
    clear_requested = pyqtSignal()

    def __init__(self, entries: list[HistoryEntry], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entries = entries
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 18)
        root.setSpacing(16)
        right = QPushButton("Очистить историю")
        right.setProperty("variant", "ghost")
        right.setIcon(icon("trash", P.dim, 15))
        right.clicked.connect(self.clear_requested.emit)
        root.addWidget(_page_header("История", "Последние сканирования и сохранённые результаты.", right, eyebrow="Архив"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(8)
        self.empty = QWidget()
        ev = QVBoxLayout(self.empty)
        ev.setContentsMargins(0, 70, 0, 0)
        ev.setSpacing(10)
        ic = QLabel()
        self.empty_icon = ic
        ic.setPixmap(icon("history", P.dim, 44).pixmap(44, 44))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(ic)
        et = QLabel("История пока пуста")
        et.setFont(font(17, QFont.Weight.DemiBold))
        et.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(et)
        ed = _muted("После первого сканирования здесь появятся сохранённые результаты.", 12)
        ed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(ed)
        self.list_layout.addWidget(self.empty)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)
        self.refresh(entries)

    def refresh_theme(self) -> None:
        self.empty_icon.setPixmap(icon("history", P.dim, 44).pixmap(44, 44))
        self.refresh(self.entries)

    def refresh(self, entries: list[HistoryEntry]) -> None:
        self.entries = entries
        for i in reversed(range(self.list_layout.count())):
            item = self.list_layout.itemAt(i)
            widget = item.widget()
            if widget is not None and widget is not self.empty:
                widget.setParent(None)
                widget.deleteLater()
        for idx, entry in enumerate(entries):
            card = HistoryCard(entry)
            card.open_clicked.connect(self.open_entry.emit)
            card.repeat_clicked.connect(self.repeat_entry.emit)
            self.list_layout.insertWidget(idx, card)
        self.empty.setVisible(not entries)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingsPage(QWidget):
    setting_changed = pyqtSignal(str, object)
    export_favorites = pyqtSignal()
    import_favorites = pyqtSignal()
    clear_history = pyqtSignal()
    about_requested = pyqtSignal()
    repository_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 18)
        root.setSpacing(16)
        root.addWidget(_page_header("Настройки", "Скорость, обнаружение сервисов и данные приложения.", eyebrow="Параметры"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(0, 0, 6, 4)
        self.layout.setSpacing(12)
        self.scroll = scroll
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # appearance
        card, cl = _settings_card("Оформление", "Светлая, тёмная или системная тема интерфейса.")
        theme_box = QWidget()
        tb = QHBoxLayout(theme_box)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(5)
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_buttons: dict[str, QPushButton] = {}
        for mode, label in (("system", "Системная"), ("dark", "Тёмная"), ("light", "Светлая")):
            btn = QPushButton(label)
            btn.setProperty("chip", "true")
            btn.setProperty("themeMode", mode)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda _=False, m=mode: self._theme_changed(m))
            self.theme_group.addButton(btn)
            self.theme_buttons[mode] = btn
            tb.addWidget(btn)
        cl.addWidget(_setting_row("Тема оформления", "Системная подстраивается под оформление Ubuntu.", theme_box))
        cl.addWidget(hline())
        self.layout.addWidget(card)

        # performance
        card, cl = _settings_card("Производительность", "Баланс между скоростью и нагрузкой на сеть и процессор.")
        speed = QWidget()
        sl = QVBoxLayout(speed)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(4)
        self.speed_value = QLabel("Сбалансированно")
        self.speed_value.setStyleSheet(f"color:{P.accent}; font-size:11px;")
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 5)
        self.speed_slider.setFixedWidth(210)
        self.speed_slider.setPageStep(1)
        self.speed_slider.valueChanged.connect(self._speed_changed)
        sl.addWidget(self.speed_slider)
        sl.addWidget(self.speed_value)
        cl.addWidget(_setting_row("Скорость сканирования", "Больше потоков — быстрее, но заметнее нагрузка.", speed))
        cl.addWidget(hline())
        self.toggle_tcp = ToggleSwitch()
        self.toggle_tcp.toggled.connect(lambda v: self._emit("tcp_discovery", v))
        cl.addWidget(_setting_row(
            "Глубокое обнаружение",
            "Проверять TCP-порты, если хост не отвечает на ICMP.",
            self.toggle_tcp,
        ))
        self.layout.addWidget(card)

        # discovery
        card, cl = _settings_card("Обнаружение", "Какие данные собирать о найденных устройствах.")
        self.toggle_services = ToggleSwitch()
        self.toggle_services.toggled.connect(lambda v: self._emit("scan_services", v))
        cl.addWidget(_setting_row("Сканировать сервисы", "HTTP, HTTPS, SMB, SSH, RDP, FTP, печать и другие порты.", self.toggle_services))
        cl.addWidget(hline())
        self.toggle_names = ToggleSwitch()
        self.toggle_names.toggled.connect(lambda v: self._emit("resolve_names", v))
        cl.addWidget(_setting_row("Определять имена", "Обратное DNS и mDNS-разрешение имён.", self.toggle_names))
        cl.addWidget(hline())
        self.toggle_netbios = ToggleSwitch()
        self.toggle_netbios.toggled.connect(lambda v: self._emit("use_netbios", v))
        cl.addWidget(_setting_row("NetBIOS", "Запрашивать имя компьютера и рабочую группу Windows.", self.toggle_netbios))
        cl.addWidget(hline())
        self.toggle_mdns = ToggleSwitch()
        self.toggle_mdns.toggled.connect(lambda v: self._emit("use_mdns", v))
        cl.addWidget(_setting_row("mDNS / Avahi", "Имена из локальных сервисов, AirPlay, принтеров и NAS.", self.toggle_mdns))
        cl.addWidget(hline())
        self.toggle_ssdp = ToggleSwitch()
        self.toggle_ssdp.toggled.connect(lambda v: self._emit("use_ssdp", v))
        cl.addWidget(_setting_row("SSDP / UPnP", "Дружественные имена телевизоров, роутеров и медиаустройств.", self.toggle_ssdp))
        cl.addWidget(hline())
        self.toggle_snmp = ToggleSwitch()
        self.toggle_snmp.toggled.connect(lambda v: self._emit("use_snmp", v))
        cl.addWidget(_setting_row("SNMP sysName", "Читать имя сетевого оборудования и принтеров (community public).", self.toggle_snmp))
        cl.addWidget(hline())
        ports_box = QWidget()
        pb = QVBoxLayout(ports_box)
        pb.setContentsMargins(0, 0, 0, 0)
        pb.setSpacing(3)
        self.ports = QLineEdit()
        self.ports.setFixedWidth(360)
        self.ports.setPlaceholderText("21,22,80,443,445,3389")
        self.ports.setProperty("mono", "true")
        self.ports.editingFinished.connect(self._ports_changed)
        hint = QLabel("Порты TCP через запятую. По умолчанию — 18 популярных сервисов.")
        hint.setStyleSheet(f"color:{P.dim}; font-size:10.5px;")
        pb.addWidget(self.ports)
        pb.addWidget(hint)
        cl.addWidget(_setting_row("Порты для проверки", "Дополнительные сервисы для обнаружения.", ports_box))
        self.layout.addWidget(card)

        # notifications
        card, cl = _settings_card("Приложение", "Поведение интерфейса и уведомления.")
        self.toggle_notify = ToggleSwitch()
        self.toggle_notify.toggled.connect(lambda v: self._emit("notify", v))
        cl.addWidget(_setting_row("Уведомления", "Показывать системное уведомление после завершения сканирования.", self.toggle_notify))
        cl.addWidget(hline())
        reset = QPushButton("Сбросить настройки")
        reset.setProperty("variant", "ghost")
        reset.clicked.connect(self.reset_requested.emit)
        cl.addWidget(_setting_row("Настройки по умолчанию", "Вернуть скорость, порты и параметры обнаружения.", reset))
        self.layout.addWidget(card)

        # data
        card, cl = _settings_card("Данные", "Избранное и история хранятся локально на этом компьютере.")
        data_row = QWidget()
        dr = QHBoxLayout(data_row)
        dr.setContentsMargins(0, 0, 0, 0)
        dr.setSpacing(6)
        exp = QPushButton("Экспорт избранного")
        exp.setIcon(icon("upload", P.muted, 14))
        exp.clicked.connect(self.export_favorites.emit)
        imp = QPushButton("Импорт")
        imp.setIcon(icon("download", P.muted, 14))
        imp.clicked.connect(self.import_favorites.emit)
        clear = QPushButton("Очистить историю")
        clear.setProperty("variant", "ghost")
        clear.clicked.connect(self.clear_history.emit)
        dr.addWidget(exp)
        dr.addWidget(imp)
        dr.addWidget(clear)
        cl.addWidget(_setting_row("Избранное и история", "Файлы находятся в ~/.config/scanero.", data_row))
        self.layout.addWidget(card)

        # about
        card, cl = _settings_card("О программе", "Scanero IP Сканер · современный сканер локальной сети для Ubuntu.")
        about_row = QWidget()
        ar = QHBoxLayout(about_row)
        ar.setContentsMargins(0, 0, 0, 0)
        ar.setSpacing(10)
        ver = QLabel(f"Версия {__version__}")
        ver.setStyleSheet(f"color:{P.muted}; font-size:11.5px;")
        ar.addWidget(ver)
        ar.addStretch(1)
        repo = QPushButton("Репозиторий")
        repo.setProperty("variant", "ghost")
        repo.setIcon(icon("external", P.muted, 14))
        repo.setCursor(Qt.CursorShape.PointingHandCursor)
        repo.clicked.connect(self.repository_requested.emit)
        ar.addWidget(repo)
        about = QPushButton("Подробнее")
        about.setIcon(icon("info", P.muted, 15))
        about.clicked.connect(self.about_requested.emit)
        ar.addWidget(about)
        cl.addWidget(about_row)
        self.layout.addWidget(card)
        self.layout.addStretch(1)
        self.refresh_from_settings()

    def _emit(self, key: str, value: object) -> None:
        if not self._loading:
            self.setting_changed.emit(key, value)

    def _speed_changed(self, value: int) -> None:
        labels = {1: "Экономно", 2: "Плавно", 3: "Сбалансированно", 4: "Быстро", 5: "Максимум"}
        self.speed_value.setText(labels.get(value, "Сбалансированно"))
        self._emit("speed", value)

    def _ports_changed(self) -> None:
        self._emit("ports", self.ports.text().strip())

    def _theme_changed(self, mode: str) -> None:
        self._emit("theme", mode)

    def refresh_theme(self) -> None:
        self.refresh_from_settings()
        self.update()

    def refresh_from_settings(self) -> None:
        self._loading = True
        try:
            self.speed_slider.setValue(int(self.settings.get("speed", 3)))
            self.speed_value.setText({1: "Экономно", 2: "Плавно", 3: "Сбалансированно", 4: "Быстро", 5: "Максимум"}.get(self.speed_slider.value(), "Сбалансированно"))
            self.toggle_tcp.setChecked(bool(self.settings.get("tcp_discovery", True)))
            self.toggle_services.setChecked(bool(self.settings.get("scan_services", True)))
            self.toggle_names.setChecked(bool(self.settings.get("resolve_names", True)))
            self.toggle_netbios.setChecked(bool(self.settings.get("use_netbios", True)))
            self.toggle_mdns.setChecked(bool(self.settings.get("use_mdns", True)))
            self.toggle_ssdp.setChecked(bool(self.settings.get("use_ssdp", True)))
            self.toggle_snmp.setChecked(bool(self.settings.get("use_snmp", True)))
            self.toggle_notify.setChecked(bool(self.settings.get("notify", True)))
            theme = str(self.settings.get("theme", "system"))
            for mode, button in self.theme_buttons.items():
                button.setChecked(mode == theme)
            self.ports.setText(str(self.settings.get("ports", "")))
            self.ports.setCursorPosition(0)
        finally:
            self._loading = False
