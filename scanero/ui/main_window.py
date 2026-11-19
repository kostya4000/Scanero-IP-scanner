"""Main application window."""
from __future__ import annotations

import json
import time
from pathlib import Path

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.actions import (
    copy_text,
    device_as_text,
    notify,
    open_rdp,
    open_service,
    open_terminal,
    open_web,
    ping_device,
    send_wol,
    ssh_device,
    trace_device,
)
from ..core.exporter import export
from ..core.models import Device, Favorite, Service
from ..core.netinfo import (
    Interface,
    describe_targets,
    list_interfaces,
    parse_targets,
)
from ..core.scanner import ScanOptions, ScanResult
from ..core.storage import HistoryEntry, SPEED_MAP, Settings, FavoritesStore, HistoryStore
from .dialogs import AboutDialog, ShutdownDialog
from .icons import icon, pixmap
from .pages import FavoritesPage, HistoryPage, ScannerPage, SettingsPage
from .theme import P, qss
from .widgets import IconButton, LogoWidget, NavButton, NetworkCard, Toast, font, plural
from .worker import ScanWorker

ASSETS = Path(__file__).resolve().parent.parent / "assets"


# ---------------------------------------------------------------------------
# Frameless shell
# ---------------------------------------------------------------------------

class RootFrame(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.maximized = False
        self.setObjectName("Root")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        radius = 0 if self.maximized else 16
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), radius, radius)
        p.setClipPath(path)

        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor("#070B13"))
        grad.setColorAt(0.5, QColor("#080D18"))
        grad.setColorAt(1.0, QColor("#0B1120"))
        p.fillPath(path, grad)

        glow1 = QRadialGradient(self.width() * 0.88, 40, max(300, self.width() * 0.55))
        glow1.setColorAt(0.0, QColor(34, 211, 238, 24))
        glow1.setColorAt(0.55, QColor(34, 211, 238, 6))
        glow1.setColorAt(1.0, QColor(34, 211, 238, 0))
        p.fillRect(self.rect(), glow1)

        glow2 = QRadialGradient(self.width() * 0.05, self.height() * 0.98, max(280, self.width() * 0.42))
        glow2.setColorAt(0.0, QColor(139, 140, 255, 18))
        glow2.setColorAt(0.55, QColor(139, 140, 255, 5))
        glow2.setColorAt(1.0, QColor(139, 140, 255, 0))
        p.fillRect(self.rect(), glow2)

        p.setClipping(False)
        border = QColor("#22334E")
        border.setAlpha(180)
        p.setPen(border)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, radius, radius)


class TitleBar(QFrame):
    minimize_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()
    close_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(54)
        self._dragging = False
        self._drag_offset = QPoint()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 10, 0)
        layout.setSpacing(10)
        layout.addWidget(LogoWidget(30))
        name = QLabel("Scanero IP Сканер")
        name.setFont(font(15, QFont.Weight.DemiBold))
        name.setStyleSheet(f"color:{P.text};")
        layout.addWidget(name)
        dot = QLabel("·")
        dot.setStyleSheet(f"color:{P.dim}; font-size:16px;")
        layout.addWidget(dot)
        tag = QLabel("Локальная сеть")
        tag.setStyleSheet(f"color:{P.dim}; font-size:11.5px;")
        layout.addWidget(tag)
        version = QLabel(f"v{__version__}")
        version.setFixedHeight(20)
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(
            "color:#6EE7F7; background:rgba(34,211,238,.08); border:1px solid rgba(34,211,238,.16);"
            "border-radius:6px; padding:0 7px; font-size:9.5px; font-weight:600;"
        )
        layout.addWidget(version, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)

        self.btn_min = self._window_button("minus", "Свернуть")
        self.btn_max = self._window_button("square", "Развернуть")
        self.btn_close = self._window_button("x", "Закрыть", close=True)
        self.btn_min.clicked.connect(self.minimize_clicked.emit)
        self.btn_max.clicked.connect(self.maximize_clicked.emit)
        self.btn_close.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

    def _window_button(self, icon_name: str, tip: str, close: bool = False) -> QPushButton:
        btn = QPushButton()
        btn.setProperty("variant", "close" if close else "window")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(32, 32)
        btn.setIcon(icon(icon_name, P.muted if not close else "#D6A4AA", 16))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(tip)
        if close:
            btn.setIcon(icon(icon_name, "#EDB5BC", 16))
        return btn

    def set_maximized(self, value: bool) -> None:
        self.btn_max.setIcon(icon("restore" if value else "square", P.muted, 15))
        self.btn_max.setToolTip("Восстановить" if value else "Развернуть")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            if not window.isMaximized():
                if QApplication.platformName() == "wayland" and window.windowHandle():
                    window.windowHandle().startSystemMove()
                else:
                    self._dragging = True
                    self._drag_offset = event.globalPosition().toPoint() - window.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.maximize_clicked.emit()
        super().mouseDoubleClickEvent(event)


class ResizeHandle(QWidget):
    def __init__(self, edges: Qt.Edge, cursor: Qt.CursorShape, parent: QWidget) -> None:
        super().__init__(parent)
        self._edges = edges
        self._resizing = False
        self._start = QPoint()
        self._geometry = QRect()
        self.setCursor(cursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            if QApplication.platformName() == "wayland" and window.windowHandle():
                window.windowHandle().startSystemResize(self._edges)
            else:
                self._resizing = True
                self._start = event.globalPosition().toPoint()
                self._geometry = window.geometry()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._resizing:
            return
        window = self.window()
        delta = event.globalPosition().toPoint() - self._start
        geo = QRect(self._geometry)
        min_w, min_h = window.minimumWidth(), window.minimumHeight()
        if self._edges & Qt.Edge.LeftEdge:
            new_left = min(geo.right() - min_w + 1, geo.left() + delta.x())
            geo.setLeft(new_left)
        if self._edges & Qt.Edge.RightEdge:
            geo.setRight(max(geo.left() + min_w - 1, geo.right() + delta.x()))
        if self._edges & Qt.Edge.TopEdge:
            new_top = min(geo.bottom() - min_h + 1, geo.top() + delta.y())
            geo.setTop(new_top)
        if self._edges & Qt.Edge.BottomEdge:
            geo.setBottom(max(geo.top() + min_h - 1, geo.bottom() + delta.y()))
        window.setGeometry(geo)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._resizing = False
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self.favorites = FavoritesStore()
        self.history = HistoryStore()
        self.interfaces: list[Interface] = []
        self.iface: Interface | None = None
        self.worker: ScanWorker | None = None
        self._scan_started = 0.0
        self._last_result: ScanResult | None = None
        self._wide = True
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(450)
        self._save_timer.timeout.connect(self.settings.save)

        self.setWindowTitle("Scanero IP Сканер")
        self.setWindowIcon(QIcon(str(ASSETS / "scanero.png")) if (ASSETS / "scanero.png").exists() else icon("radar", P.accent, 32))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(1120, 700)
        self.setStyleSheet(qss())

        self.root = RootFrame(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.root)

        root_layout = QVBoxLayout(self.root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.titlebar = TitleBar()
        self.titlebar.minimize_clicked.connect(self.showMinimized)
        self.titlebar.maximize_clicked.connect(self._toggle_maximize)
        self.titlebar.close_clicked.connect(self.close)
        root_layout.addWidget(self.titlebar)

        body = QHBoxLayout()
        body.setContentsMargins(10, 0, 10, 10)
        body.setSpacing(10)
        root_layout.addLayout(body, 1)

        # --- sidebar --------------------------------------------------------
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(228)
        self.sidebar.setStyleSheet(
            "QFrame#Sidebar { background: rgba(9, 14, 25, 0.7); border: 1px solid #152134;"
            " border-radius: 14px; }"
        )
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(12, 14, 12, 12)
        side.setSpacing(4)
        nav_label = QLabel("НАВИГАЦИЯ")
        nf = font(9.2, QFont.Weight.DemiBold)
        nf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.3)
        nav_label.setFont(nf)
        nav_label.setStyleSheet(f"color:{P.dim}; margin-left:8px; margin-bottom:4px;")
        side.addWidget(nav_label)

        self.nav: dict[str, NavButton] = {}
        for key, label, icon_name in (
            ("scanner", "Сканер", "radar"),
            ("favorites", "Избранное", "star"),
            ("history", "История", "history"),
        ):
            btn = NavButton(icon_name, label)
            btn.clicked.connect(lambda _=False, k=key: self.switch_page(k))
            side.addWidget(btn)
            self.nav[key] = btn
        side.addStretch(1)

        self.network_card = NetworkCard()
        side.addWidget(self.network_card)
        self.network_card.clicked.connect(self._show_interface_menu)
        side.addSpacing(8)
        side.addWidget(self._divider())
        self.nav_settings = NavButton("settings", "Настройки")
        self.nav_settings.clicked.connect(lambda: self.switch_page("settings"))
        side.addWidget(self.nav_settings)
        footer = QLabel(f"Scanero IP · {__version__}\nUbuntu Edition")
        footer.setStyleSheet(f"color:{P.dim}; font-size:9.5px; line-height:1.5;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(footer)
        body.addWidget(self.sidebar)

        # --- pages ----------------------------------------------------------
        self.stack = QStackedWidget()
        self.stack.setObjectName("Content")
        self.scanner = ScannerPage(self.settings, self.favorites.items)
        self.favorites_page = FavoritesPage(self.favorites.items)
        self.history_page = HistoryPage(self.history.items)
        self.settings_page = SettingsPage(self.settings)
        for page in (self.scanner, self.favorites_page, self.history_page, self.settings_page):
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)

        # --- wiring ---------------------------------------------------------
        self.scanner.scan_requested.connect(self.start_scan)
        self.scanner.stop_requested.connect(self.stop_scan)
        self.scanner.action_requested.connect(self._handle_action)
        self.scanner.service_requested.connect(self._open_service)
        self.scanner.favorite_toggled.connect(self.toggle_favorite)
        self.scanner.export_requested.connect(self.export_report)
        self.scanner.settings_requested.connect(lambda: self.switch_page("settings"))
        self.scanner.range_changed.connect(self._range_changed)
        self.scanner.filter_changed.connect(self._filter_changed)

        self.favorites_page.scan_single.connect(self._scan_favorite)
        self.favorites_page.scan_all.connect(self._scan_favorites)
        self.favorites_page.remove_requested.connect(self._remove_favorite)
        self.settings_page.setting_changed.connect(self._setting_changed)
        self.settings_page.export_favorites.connect(self._export_favorites)
        self.settings_page.import_favorites.connect(self._import_favorites)
        self.settings_page.clear_history.connect(self._clear_history)
        self.settings_page.about_requested.connect(self._show_about)
        self.settings_page.reset_requested.connect(self._reset_settings)
        self.history_page.open_entry.connect(self._open_history)
        self.history_page.repeat_entry.connect(self._repeat_history)
        self.history_page.clear_requested.connect(self._clear_history)

        # --- overlay / chrome ----------------------------------------------
        self.toast = Toast(self.root)
        self.handles = [
            ResizeHandle(Qt.Edge.LeftEdge, Qt.CursorShape.SizeHorCursor, self),
            ResizeHandle(Qt.Edge.RightEdge, Qt.CursorShape.SizeHorCursor, self),
            ResizeHandle(Qt.Edge.TopEdge, Qt.CursorShape.SizeVerCursor, self),
            ResizeHandle(Qt.Edge.BottomEdge, Qt.CursorShape.SizeVerCursor, self),
            ResizeHandle(Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.CursorShape.SizeFDiagCursor, self),
            ResizeHandle(Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.CursorShape.SizeBDiagCursor, self),
            ResizeHandle(Qt.Edge.LeftEdge | Qt.Edge.BottomEdge, Qt.CursorShape.SizeBDiagCursor, self),
            ResizeHandle(Qt.Edge.RightEdge | Qt.Edge.BottomEdge, Qt.CursorShape.SizeFDiagCursor, self),
        ]

        self._install_shortcuts()
        self._refresh_interfaces(initial=True)
        self._refresh_favorites_ui()
        self._restore_geometry()
        self.switch_page("scanner")
        QTimer.singleShot(80, self._sync_inspector)

    # -- helpers -------------------------------------------------------------
    def _divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("Divider")
        line.setFixedHeight(1)
        return line

    def _install_shortcuts(self) -> None:
        def sc(seq: str, fn) -> None:
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.activated.connect(fn)

        sc("F5", self._scan_or_stop)
        sc("Ctrl+F", self._focus_search)
        sc("Ctrl+E", lambda: self.export_report("csv"))
        sc("Ctrl+,", lambda: self.switch_page("settings"))
        sc("Ctrl+1", lambda: self.switch_page("scanner"))
        sc("Ctrl+2", lambda: self.switch_page("favorites"))
        sc("Ctrl+3", lambda: self.switch_page("history"))
        sc("Ctrl+Q", self.close)
        sc("Esc", self._escape)

    def _escape(self) -> None:
        if self.worker is not None:
            self.stop_scan()
        elif self.scanner.search.text():
            self.scanner.search.clear()
        else:
            self.scanner.tree.clearSelection()

    def _focus_search(self) -> None:
        if self.stack.currentWidget() is self.scanner:
            self.scanner.search.setFocus()
            self.scanner.search.selectAll()

    def _scan_or_stop(self) -> None:
        if self.worker is not None:
            self.stop_scan()
        elif self.stack.currentWidget() is self.scanner:
            self.start_scan(self.scanner.range_edit.text().strip())

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            maximized = self.isMaximized()
            self.root.maximized = maximized
            self.root.update()
            self.titlebar.set_maximized(maximized)
            self._layout_handles()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout_handles()
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast._reposition()
        self._sync_inspector()

    def _layout_handles(self) -> None:
        if not hasattr(self, "handles"):
            return
        w, h = self.width(), self.height()
        m = 5
        c = 11
        maximized = self.isMaximized()
        for handle in self.handles:
            handle.setVisible(not maximized)
        if maximized:
            return
        self.handles[0].setGeometry(0, c, m, max(0, h - 2 * c))  # left
        self.handles[1].setGeometry(w - m, c, m, max(0, h - 2 * c))  # right
        self.handles[2].setGeometry(c, 0, max(0, w - 2 * c), m)  # top
        self.handles[3].setGeometry(c, h - m, max(0, w - 2 * c), m)  # bottom
        self.handles[4].setGeometry(0, 0, c, c)
        self.handles[5].setGeometry(w - c, 0, c, c)
        self.handles[6].setGeometry(0, h - c, c, c)
        self.handles[7].setGeometry(w - c, h - c, c, c)
        for handle in self.handles:
            handle.raise_()

    def _sync_inspector(self) -> None:
        if not hasattr(self, "scanner"):
            return
        wide = self.width() >= 1320
        if wide != self._wide:
            self._wide = wide
            self.scanner.inspector_btn.setChecked(wide)
            self.scanner.inspector.setVisible(wide)

    def _restore_geometry(self) -> None:
        screen = QApplication.primaryScreen()
        geometry = screen.availableGeometry() if screen else QRect(0, 0, 1600, 950)
        size = self.settings.get("window_size", [1460, 900])
        width = min(int(size[0]), int(geometry.width() * 0.95))
        height = min(int(size[1]), int(geometry.height() * 0.95))
        self.resize(max(1120, width), max(700, height))
        pos = self.settings.get("window_pos", [])
        if isinstance(pos, list) and len(pos) == 2:
            x = min(max(int(pos[0]), geometry.left()), geometry.right() - self.width() + 1)
            y = min(max(int(pos[1]), geometry.top()), geometry.bottom() - self.height() + 1)
            self.move(x, y)
        else:
            self.move(geometry.center() - self.rect().center())

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(2500)
        if self.isMaximized():
            geometry = self.normalGeometry()
            size = [geometry.width(), geometry.height()]
            pos = [geometry.x(), geometry.y()]
        else:
            size = [self.width(), self.height()]
            pos = [self.x(), self.y()]
        self.settings.update({"window_size": size, "window_pos": pos})
        super().closeEvent(event)

    # -- pages ---------------------------------------------------------------
    def switch_page(self, key: str) -> None:
        mapping = {
            "scanner": (self.scanner, 0),
            "favorites": (self.favorites_page, 1),
            "history": (self.history_page, 2),
            "settings": (self.settings_page, 3),
        }
        page, idx = mapping.get(key, mapping["scanner"])
        self.stack.setCurrentIndex(idx)
        for nav_key, btn in self.nav.items():
            btn.set_active(nav_key == key)
        self.nav_settings.set_active(key == "settings")
        if key == "favorites":
            self.favorites_page.refresh(self.favorites.items)
        elif key == "history":
            self.history_page.refresh(self.history.items)
        elif key == "settings":
            self.settings_page.refresh_from_settings()
        self.settings.set("last_page", key, save=False)
        self._save_timer.start()

    # -- interfaces ----------------------------------------------------------
    def _refresh_interfaces(self, initial: bool = False) -> None:
        self.interfaces = list_interfaces()
        saved = self.settings.get("interface", "")
        chosen = next((i for i in self.interfaces if i.name == saved), None)
        if chosen is None and self.interfaces:
            chosen = self.interfaces[0]
        self.iface = chosen
        if chosen:
            self.settings.set("interface", chosen.name, save=False)
        self.network_card.set_interface(chosen)
        self.scanner.set_interface(chosen, self.interfaces)
        saved_range = self.settings.get("range", "")
        if initial and saved_range:
            self.scanner.range_edit.setText(saved_range)
        self.scanner._update_idle_text()

    def _show_interface_menu(self) -> None:
        if self.worker is not None:
            self.toast.show_message("Сначала остановите сканирование", "error")
            return
        self.interfaces = list_interfaces()
        menu = QMenu(self)
        for iface in self.interfaces:
            title = f"{iface.title}" + (f" · {iface.ssid}" if iface.ssid else "")
            action = menu.addAction(
                icon("wifi" if iface.wireless else "ethernet", P.accent if iface is self.iface else P.muted, 15),
                f"{title}   {iface.ip}/{iface.prefix}",
            )
            action.triggered.connect(lambda _=False, i=iface: self._select_interface(i))
        if not self.interfaces:
            action = menu.addAction("Интерфейсы не найдены")
            action.setEnabled(False)
        menu.addSeparator()
        refresh = menu.addAction(icon("refresh", P.muted, 15), "Обновить список сетей")
        refresh.triggered.connect(self._refresh_interfaces)
        if self.iface and self.iface.whole_subnet != self.iface.default_range:
            whole = menu.addAction(icon("target", P.muted, 15), f"Сканировать всю подсеть {self.iface.whole_subnet}")
            whole.triggered.connect(lambda: self._scan_with_range(self.iface.whole_subnet))
        menu.exec(self.network_card.mapToGlobal(self.network_card.rect().topRight()))
        self.network_card.set_interface(self.iface)

    def _select_interface(self, iface: Interface) -> None:
        if self.worker is not None:
            self.toast.show_message("Сначала остановите сканирование", "error")
            return
        self.iface = iface
        self.settings.set("interface", iface.name, save=False)
        self.settings.set("range", iface.default_range, save=False)
        self._save_timer.start()
        self.network_card.set_interface(iface)
        self.scanner.set_interface(iface, self.interfaces)
        self.scanner.range_edit.setText(iface.default_range)
        self.toast.show_message(f"Сеть: {iface.title}", "info")

    def _range_changed(self, text: str) -> None:
        self.settings.set("range", text, save=False)
        self._save_timer.start()

    def _filter_changed(self, mode: str) -> None:
        self.settings.set("filter", mode, save=False)
        self._save_timer.start()

    # -- scanning ------------------------------------------------------------
    def start_scan(self, expr: str | None = None) -> None:
        if self.worker is not None:
            self.toast.show_message("Сканирование уже выполняется", "info")
            return
        expr = (expr or self.scanner.range_edit.text() or "").strip()
        if not expr:
            self.toast.show_message("Введите диапазон IP-адресов", "error")
            self.scanner.range_edit.setFocus()
            return
        try:
            targets = parse_targets(expr, self.interfaces)
        except ValueError as exc:
            self.toast.show_message(str(exc), "error")
            return
        if len(targets) > 4096:
            answer = QMessageBox.question(
                self,
                "Большой диапазон",
                f"Будет просканировано {len(targets)} адресов. Это может занять несколько минут.\n\nПродолжить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.scanner.range_edit.setText(expr)
        self.settings.set("range", expr, save=False)
        self._save_timer.start()
        self.scanner.search.blockSignals(True)
        self.scanner.search.clear()
        self.scanner.search.blockSignals(False)
        self.scanner.proxy.set_search("")
        self.scanner.reset_results()
        self.scanner.set_scanning(True)
        self.scanner.stack.setCurrentIndex(0)
        self.scanner.status_label.setText(f"Сканирование {describe_targets(targets)}…")
        self.scanner.footer_info.setText("")

        speed = SPEED_MAP.get(int(self.settings.get("speed", 3)), SPEED_MAP[3])
        options = ScanOptions(
            threads=int(speed["threads"]),
            ping_timeout=float(speed["ping_timeout"]),
            port_timeout=float(speed["port_timeout"]),
            scan_services=bool(self.settings.get("scan_services", True)),
            resolve_names=bool(self.settings.get("resolve_names", True)),
            use_netbios=bool(self.settings.get("use_netbios", True)),
            use_mdns=bool(self.settings.get("use_mdns", True)),
            tcp_discovery=bool(self.settings.get("tcp_discovery", True)),
            ports=self.settings.ports,
            interfaces=self.interfaces,
        )
        self.worker = ScanWorker(targets, options, expr, self)
        self.worker.found.connect(self.scanner.on_found)
        self.worker.updated.connect(self.scanner.on_updated)
        self.worker.progress.connect(self.scanner.on_progress)
        self.worker.result.connect(self._scan_finished)
        self.worker.failed.connect(self._scan_failed)
        self.worker.finished.connect(self.worker.deleteLater)
        self._scan_started = time.time()
        self._last_result = None
        self.worker.start()
        self.toast.show_message(
            f"Сканируем {len(targets)} {plural(len(targets), 'адрес', 'адреса', 'адресов')} · "
            f"{describe_targets(targets)}",
            "info",
        )

    def stop_scan(self) -> None:
        if self.worker is None:
            return
        self.worker.stop()
        self.scanner.status_label.setText("Останавливаем сканирование…")
        self.scanner.scan_btn.setEnabled(False)
        QTimer.singleShot(1500, lambda: self.scanner.scan_btn.setEnabled(True))

    def _scan_finished(self, result: ScanResult) -> None:
        self.worker = None
        self._last_result = result
        self.scanner.on_result(result)
        self.scanner.scan_btn.setEnabled(True)
        if not result.cancelled:
            self._record_history(result)
            self._touch_favorites(result)
            if bool(self.settings.get("notify", True)):
                notify(
                    "Scanero IP Сканер · сканирование завершено",
                    f"{result.online} {plural(result.online, 'устройство', 'устройства', 'устройств')} в сети, "
                    f"{result.services} {plural(result.services, 'сервис', 'сервиса', 'сервисов')} "
                    f"за {result.duration:.1f} с",
                )
            self.toast.show_message(
                f"Готово: {result.online} {plural(result.online, 'устройство', 'устройства', 'устройств')} · "
                f"{result.services} {plural(result.services, 'сервис', 'сервиса', 'сервисов')} · "
                f"{result.duration:.1f} с",
                "ok",
            )
        else:
            self.toast.show_message("Сканирование остановлено", "info")
        self._refresh_favorites_ui()
        self.scanner._update_counts()

    def _scan_failed(self, message: str) -> None:
        self.worker = None
        self.scanner.set_scanning(False)
        self.scanner.progress.setVisible(False)
        self.scanner.scan_btn.setEnabled(True)
        self.scanner.status_label.setText("Ошибка сканирования")
        self.scanner._update_empty_state()
        self.toast.show_message(f"Ошибка: {message}", "error")

    def _record_history(self, result: ScanResult) -> None:
        online_devices = [d.to_dict() for d in result.devices if d.is_online()]
        entry = HistoryEntry(
            id=str(int(time.time() * 1000)),
            timestamp=time.time(),
            range_expr=result.range_expr,
            target_count=result.target_count,
            online=result.online,
            offline=result.offline,
            services=result.services,
            duration=result.duration,
            devices=online_devices,
        )
        self.history.add(entry)
        self.history_page.refresh(self.history.items)

    def _touch_favorites(self, result: ScanResult) -> None:
        changed = False
        for device in result.devices:
            if not device.is_online():
                continue
            fav = self.favorites.find(device)
            if fav:
                fav.ip = device.ip or fav.ip
                fav.mac = device.mac or fav.mac
                fav.name = device.name or fav.name
                fav.vendor = device.vendor or fav.vendor
                fav.kind = device.kind or fav.kind
                fav.os_name = device.os_name or fav.os_name
                fav.last_seen = time.time()
                changed = True
        if changed:
            self.favorites.save()

    def _scan_with_range(self, expr: str) -> None:
        self.switch_page("scanner")
        self.scanner.range_edit.setText(expr)
        self.start_scan(expr)

    def _scan_favorite(self, ip: str) -> None:
        self._scan_with_range(ip)

    def _scan_favorites(self, expr: str) -> None:
        self._scan_with_range(expr)

    # -- actions -------------------------------------------------------------
    def _handle_action(self, action: str, device: Device) -> None:
        if action == "favorite":
            self.toggle_favorite(device)
            return
        if action == "copy":
            copy_text(device_as_text(device))
            self.toast.show_message("Сведения скопированы", "ok")
            return
        if action == "wol":
            if not device.mac:
                self.toast.show_message("Неизвестен MAC-адрес для Wake-on-LAN", "error")
                return
            ok, msg = send_wol(device.mac)
            self.toast.show_message(
                f"Wake-on-LAN: {device.mac}" if ok else msg, "ok" if ok else "error"
            )
            return
        if action == "shutdown":
            ShutdownDialog(device, self).exec()
            return
        if action == "ping":
            ok, msg = ping_device(device.ip)
            if not ok:
                self.toast.show_message(msg, "error")
            return
        if action == "trace":
            ok, msg = trace_device(device.ip)
            if not ok:
                self.toast.show_message(msg, "error")
            return
        if action == "smb":
            service = next(
                (s for kind in ("smb", "netbios", "afp", "ftp") for s in device.services if s.kind == kind),
                None,
            )
            if service:
                self._open_service(device, service)
            else:
                self.toast.show_message("Общие ресурсы не обнаружены", "error")
            return
        if action == "http":
            ok, msg = open_web(device)
            if not ok:
                self.toast.show_message(msg, "error")
            return
        if action == "rdp":
            ok, msg = open_rdp(device.ip)
            if not ok:
                self.toast.show_message(msg, "error")
            return
        if action == "ssh":
            ok, msg = ssh_device(device.ip)
            if not ok:
                self.toast.show_message(msg, "error")
            return
        if action == "open_primary":
            if not device.is_online():
                self.toast.show_message("Устройство не в сети", "error")
                return
            service = device.primary_service
            if service is None:
                if device.service_kinds & {"http", "https"}:
                    ok, msg = open_web(device)
                else:
                    self.toast.show_message("У устройства не найдено открытых сервисов", "info")
                    return
            else:
                ok, msg = open_service(device, service)
            if not ok:
                self.toast.show_message(msg, "error")
            return

    def _open_service(self, device: Device, service: Service) -> None:
        ok, msg = open_service(device, service)
        if not ok:
            self.toast.show_message(msg, "error")

    def toggle_favorite(self, device: Device) -> None:
        existing = self.favorites.find(device)
        if existing:
            self.favorites.remove(existing)
            added = False
        else:
            self.favorites.add(device)
            added = True
        self._refresh_favorites_ui()
        self.scanner.set_favorites(self.favorites.items)
        self.toast.show_message("Добавлено в избранное" if added else "Удалено из избранного", "ok")

    def _remove_favorite(self, favorite: Favorite) -> None:
        self.favorites.remove(favorite)
        self._refresh_favorites_ui()
        self.scanner.set_favorites(self.favorites.items)
        self.toast.show_message("Устройство удалено из избранного", "info")

    def _refresh_favorites_ui(self) -> None:
        count = len(self.favorites.items)
        self.nav["favorites"].set_badge(str(count) if count else "")
        self.favorites_page.refresh(self.favorites.items)
        self.scanner.set_favorites(self.favorites.items)
        self.scanner._update_counts()

    # -- history -------------------------------------------------------------
    def _open_history(self, entry: HistoryEntry) -> None:
        if self.worker is not None:
            self.toast.show_message("Сначала остановите текущее сканирование", "error")
            return
        self.switch_page("scanner")
        self.scanner.load_snapshot(entry)
        self.toast.show_message(f"Загружен снимок от {entry.date_label}", "info")

    def _repeat_history(self, entry: HistoryEntry) -> None:
        self._scan_with_range(entry.range_expr)

    def _clear_history(self) -> None:
        if not self.history.items:
            self.toast.show_message("История уже пуста", "info")
            return
        answer = QMessageBox.question(
            self,
            "Очистить историю",
            "Удалить все сохранённые результаты сканирований?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self.history_page.refresh([])
            self.toast.show_message("История очищена", "ok")

    # -- export --------------------------------------------------------------
    def export_report(self, fmt: str = "csv") -> None:
        devices = self.scanner.model.devices()
        online = [d for d in devices if d.is_online()]
        if not online:
            self.toast.show_message("Нет данных для экспорта", "error")
            return
        fmt = fmt.lower()
        ext = "html" if fmt == "html" else fmt
        default_dir = self.settings.get("export_dir", "") or str(Path.home())
        default = str(Path(default_dir) / f"scanero_{time.strftime('%Y%m%d_%H%M')}.{ext}")
        filters = {
            "csv": "CSV (*.csv)",
            "json": "JSON (*.json)",
            "html": "HTML (*.html)",
        }
        path, chosen_filter = QFileDialog.getSaveFileName(
            self, "Экспорт отчёта", default, ";;".join(filters.values())
        )
        if not path:
            return
        if "CSV" in chosen_filter:
            fmt = "csv"
        elif "JSON" in chosen_filter:
            fmt = "json"
        elif "HTML" in chosen_filter:
            fmt = "html"
        ext = "html" if fmt == "html" else fmt
        if not path.lower().endswith("." + ext):
            if Path(path).suffix.lower().lstrip(".") in {"csv", "json", "html"}:
                path = str(Path(path).with_suffix("." + ext))
            else:
                path += "." + ext
        meta = {
            "range": self.scanner.range_edit.text().strip(),
            "duration": self._last_result.duration if self._last_result else 0,
            "online": len(online),
        }
        try:
            export(path, devices, fmt, meta)
        except Exception as exc:
            self.toast.show_message(f"Не удалось сохранить: {exc}", "error")
            return
        self.settings.set("export_dir", str(Path(path).parent), save=False)
        self._save_timer.start()
        self.toast.show_message(f"Отчёт сохранён: {Path(path).name}", "ok")

    def _export_favorites(self) -> None:
        if not self.favorites.items:
            self.toast.show_message("Список избранного пуст", "error")
            return
        default = str(Path.home() / f"scanero_favorites_{time.strftime('%Y%m%d')}.json")
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт избранного", default, "JSON (*.json)")
        if not path:
            return
        try:
            payload = {
                "application": "Scanero",
                "version": 1,
                "favorites": [f.to_dict() for f in self.favorites.items],
            }
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.toast.show_message(f"Экспортировано: {len(self.favorites.items)}", "ok")
        except Exception as exc:
            self.toast.show_message(f"Ошибка экспорта: {exc}", "error")

    def _import_favorites(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Импорт избранного", str(Path.home()), "JSON (*.json)")
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            count = self.favorites.import_data(payload)
            self._refresh_favorites_ui()
            self.toast.show_message(f"Импортировано устройств: {count}", "ok")
        except Exception as exc:
            self.toast.show_message(f"Ошибка импорта: {exc}", "error")

    # -- settings ------------------------------------------------------------
    def _setting_changed(self, key: str, value: object) -> None:
        if key == "speed":
            speed = SPEED_MAP.get(int(value), SPEED_MAP[3])
            self.settings.set("speed", int(value), save=False)
            self.settings.set("threads", speed["threads"], save=False)
            self.settings.set("ping_timeout", speed["ping_timeout"], save=False)
            self.settings.set("port_timeout", speed["port_timeout"], save=False)
        elif key == "ports":
            self.settings.set("ports", str(value), save=False)
        else:
            self.settings.set(key, value, save=False)
        self._save_timer.start()

    def _reset_settings(self) -> None:
        from ..core.storage import DEFAULT_SETTINGS
        keep = {
            "range": self.scanner.range_edit.text(),
            "interface": self.iface.name if self.iface else "",
            "window_size": [self.width(), self.height()],
            "window_pos": [self.x(), self.y()],
        }
        self.settings.data = dict(DEFAULT_SETTINGS)
        self.settings.data.update(keep)
        self.settings.save()
        self.settings_page.refresh_from_settings()
        self.scanner.set_filter(self.settings.get("filter", "online"))
        self.toast.show_message("Настройки сброшены", "ok")

    def _show_about(self) -> None:
        AboutDialog(self).exec()
