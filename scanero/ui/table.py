"""Device tree model, filter proxy and custom delegate."""
from __future__ import annotations

import ipaddress
import time
from typing import Iterable

from PyQt6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QSortFilterProxyModel,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
    QStandardItem,
    QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QWidget,
)

from ..i18n import tr, translate_text
from ..core.models import Device, Service, ip_to_int, kind_label
from .icons import pixmap
from .theme import P, kind_color, service_color
from .widgets import font

ROLE_DEVICE = Qt.ItemDataRole.UserRole + 10
ROLE_SERVICE = Qt.ItemDataRole.UserRole + 11

COLUMNS = ["Устройство", "IP-адрес", "MAC-адрес", "Статус", "Сервисы"]
COL_DEVICE, COL_IP, COL_MAC, COL_STATUS, COL_SERVICES = range(5)

SERVICE_SHORT = {
    "http": "HTTP", "https": "HTTPS", "smb": "SMB", "ssh": "SSH", "rdp": "RDP",
    "ftp": "FTP", "ipp": "IPP", "lpd": "LPD", "printer": "PRINT", "vnc": "VNC",
    "dns": "DNS", "rpc": "RPC", "netbios": "NBT", "telnet": "TELNET",
    "afp": "AFP", "rtsp": "RTSP", "iphone": "SYNC",
}


def favorite_key(device: Device) -> str:
    return (device.mac or device.ip).upper()


class DeviceModel(QStandardItemModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels(COLUMNS)
        self._devices: dict[str, Device] = {}
        self._items: dict[str, QStandardItem] = {}
        self._expanded: set[str] = set()

    # -- API -----------------------------------------------------------------
    def clear_devices(self) -> None:
        self.clear()
        self.setHorizontalHeaderLabels(COLUMNS)
        self._devices.clear()
        self._items.clear()
        self._expanded.clear()

    def device_by_ip(self, ip: str) -> Device | None:
        return self._devices.get(ip)

    def devices(self) -> list[Device]:
        return list(self._devices.values())

    def online_count(self) -> int:
        return sum(1 for d in self._devices.values() if d.is_online())

    def offline_count(self) -> int:
        return sum(1 for d in self._devices.values() if d.status == "offline")

    def services_count(self) -> int:
        return sum(len(d.services) for d in self._devices.values() if d.is_online())

    def with_services_count(self) -> int:
        return sum(1 for d in self._devices.values() if d.is_online() and d.services)

    def add_or_update(self, device: Device) -> None:
        existing = self._devices.get(device.ip)
        if existing is None:
            self._devices[device.ip] = device
            self._insert(device)
        else:
            # Preserve the note/favorite marker when the scanner sends a copy.
            if existing.note and not device.note:
                device.note = existing.note
            device.favorite = existing.favorite or device.favorite
            self._devices[device.ip] = device
            self._refresh(device)

    def set_all(self, devices: Iterable[Device]) -> None:
        self.clear_devices()
        for device in devices:
            self.add_or_update(device)

    def set_favorite_flags(self, keys: set[str]) -> None:
        for ip, device in self._devices.items():
            device.favorite = favorite_key(device) in keys or device.ip in keys
            item = self._items.get(ip)
            if item:
                item.setData(device, ROLE_DEVICE)

    def remove_device(self, ip: str) -> None:
        item = self._items.pop(ip, None)
        self._devices.pop(ip, None)
        if item is not None:
            row = item.row()
            self.removeRow(row)
            # Row indexes shifted: rebuild the index map.
            self._items = {}
            for row in range(self.rowCount()):
                item = self.item(row, 0)
                device = item.data(ROLE_DEVICE) if item else None
                if isinstance(device, Device):
                    self._items[device.ip] = item

    # -- internals -----------------------------------------------------------
    def _insert(self, device: Device) -> None:
        items = [QStandardItem() for _ in range(len(COLUMNS))]
        for col, item in enumerate(items):
            item.setEditable(False)
            item.setSelectable(True)
            item.setData(device, ROLE_DEVICE)
        items[COL_DEVICE].setToolTip(
            translate_text(
                f"{device.title or 'Без имени'}\n{device.ip}\n"
                f"{device.vendor or 'Производитель неизвестен'}"
            )
        )
        self._fill_texts(items, device)
        self.appendRow(items)
        self._items[device.ip] = items[0]
        self._sync_children(items[0], device)

    def _refresh(self, device: Device) -> None:
        item = self._items.get(device.ip)
        if item is None:
            return
        row = item.row()
        cells = []
        for col in range(len(COLUMNS)):
            cell = self.item(row, col)
            if cell is not None:
                cell.setData(device, ROLE_DEVICE)
                cells.append(cell)
            else:
                cells.append(QStandardItem())
        self._fill_texts(cells, device)
        item.setToolTip(
            translate_text(
                f"{device.title or 'Без имени'}\n{device.ip}\n"
                f"{device.vendor or 'Производитель неизвестен'}"
            )
        )
        self._sync_children(item, device)
        top_left = self.index(row, 0)
        bottom_right = self.index(row, len(COLUMNS) - 1)
        self.dataChanged.emit(top_left, bottom_right)

    def _fill_texts(self, items: list[QStandardItem], device: Device) -> None:
        items[COL_DEVICE].setText(device.title or "Без имени")
        items[COL_IP].setText(device.ip)
        items[COL_MAC].setText(device.mac)
        items[COL_STATUS].setText(device.status_label)
        items[COL_SERVICES].setText(", ".join(s.name for s in device.services))
        for item in items:
            item.setEditable(False)

    def _sync_children(self, parent_item: QStandardItem, device: Device) -> None:
        desired = sorted(device.services, key=lambda s: s.port)
        current = parent_item.rowCount()
        # Remove extra rows
        if current > len(desired):
            parent_item.removeRows(len(desired), current - len(desired))
        for idx, service in enumerate(desired):
            if idx < parent_item.rowCount():
                child = parent_item.child(idx, 0)
                self._update_child_row(parent_item, idx, service)
                continue
            child_items = [QStandardItem() for _ in range(len(COLUMNS))]
            for item in child_items:
                item.setEditable(False)
            parent_item.appendRow(child_items)
            self._update_child_row(parent_item, idx, service)

    def _update_child_row(self, parent_item: QStandardItem, row: int, service: Service) -> None:
        data = service.to_dict()
        values = [
            service.name,
            f"порт {service.port}",
            "",
            "",
            service.product or service.title or "",
        ]
        for col in range(len(COLUMNS)):
            child = parent_item.child(row, col)
            if child is None:
                child = QStandardItem()
                child.setEditable(False)
                parent_item.setChild(row, col, child)
            child.setData(data, ROLE_SERVICE)
            child.setText(values[col])
            child.setEditable(False)
        parent_item.child(row, 0).setToolTip(translate_text(
            f"{service.display_name} · {tr('порт')} {service.port}"
            + (f"\n{service.product}" if service.product else "")
        ))


class DeviceFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDynamicSortFilter(True)
        self._mode = "online"
        self._search = ""
        self._favorites: set[str] = set()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.invalidateFilter()

    def set_search(self, text: str) -> None:
        self._search = (text or "").strip().lower()
        self.invalidateFilter()

    def set_favorites(self, keys: set[str]) -> None:
        self._favorites = {k.upper() for k in keys}
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if source_parent.isValid():
            return True
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        device: Device | None = index.data(ROLE_DEVICE)
        if device is None:
            return False
        if self._mode == "online" and not device.is_online():
            return False
        if self._mode == "offline" and device.status != "offline":
            return False
        if self._mode == "services" and not (device.is_online() and device.services):
            return False
        if self._mode == "favorites":
            if not ((device.mac or "").upper() in self._favorites or device.ip in self._favorites):
                return False
        if self._search:
            haystack = device.search_text
            if self._search not in haystack:
                # Also match child rows (service product/port).
                for service in device.services:
                    if self._search in service.name.lower() or self._search in service.product.lower():
                        break
                else:
                    return False
        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        if left.parent().isValid() and right.parent().isValid():
            a = left.sibling(left.row(), 0).data(ROLE_SERVICE) or {}
            b = right.sibling(right.row(), 0).data(ROLE_SERVICE) or {}
            return int(a.get("port", 0)) < int(b.get("port", 0))

        a_dev: Device | None = left.sibling(left.row(), 0).data(ROLE_DEVICE)
        b_dev: Device | None = right.sibling(right.row(), 0).data(ROLE_DEVICE)
        if a_dev is None or b_dev is None:
            return False
        col = left.column()
        if col == COL_IP:
            return ip_to_int(a_dev.ip) < ip_to_int(b_dev.ip)
        if col == COL_MAC:
            return (a_dev.mac or "z") < (b_dev.mac or "z")
        if col == COL_STATUS:
            order = {"online": 0, "unknown": 1, "offline": 2}
            return order.get(a_dev.status, 3) < order.get(b_dev.status, 3)
        if col == COL_SERVICES:
            return len(a_dev.services) < len(b_dev.services)
        return (a_dev.title or "~").lower() < (b_dev.title or "~").lower()


class HeaderView(QHeaderView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        self.setSortIndicatorShown(False)
        self.setFixedHeight(40)
        self.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def paintSection(self, painter: QPainter, rect: QRect, logical_index: int) -> None:  # noqa: N802
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(rect, Qt.GlobalColor.transparent)
        painter.setPen(QPen(QColor(P.border_soft), 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        model = self.model()
        label = model.headerData(logical_index, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) if model else ""
        label = label or ""
        active = self.sortIndicatorSection() == logical_index
        painter.setFont(font(9.6, QFont.Weight.DemiBold))
        painter.setPen(QColor(P.accent if active else P.dim))
        fm = QFontMetrics(painter.font())
        pad = 40 if logical_index == 0 else 14
        text = tr(str(label)).upper()
        text = fm.elidedText(text, Qt.TextElideMode.ElideRight, rect.width() - pad - 18)
        painter.drawText(
            rect.adjusted(pad, 0, -10, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )
        if active:
            up = self.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
            icon_name = "chevron-up" if up else "chevron-down"
            painter.drawPixmap(
                QRect(rect.right() - 20, rect.center().y() - 7, 14, 14),
                pixmap(icon_name, P.accent if active else P.dim, 14),
            )
        painter.restore()


class DeviceDelegate(QStyledItemDelegate):
    def __init__(self, tree: "DeviceTree") -> None:
        super().__init__(tree)
        self.tree = tree
        self.f_name = font(12.6, QFont.Weight.DemiBold)
        self.f_sub = font(10.4, QFont.Weight.Normal)
        self.f_ip = font(11.3, QFont.Weight.Medium, "JetBrains Mono")
        self.f_mac = font(10.6, QFont.Weight.Normal, "JetBrains Mono")
        self.f_chip = font(9.3, QFont.Weight.DemiBold)
        self.f_pill = font(10.2, QFont.Weight.DemiBold)
        self.f_service = font(11.7, QFont.Weight.DemiBold)
        self.f_small = font(9.8, QFont.Weight.Medium)

    def refresh_fonts(self) -> None:
        self.f_name = font(12.6, QFont.Weight.DemiBold)
        self.f_sub = font(10.4, QFont.Weight.Normal)
        self.f_ip = font(11.3, QFont.Weight.Medium, "JetBrains Mono")
        self.f_mac = font(10.6, QFont.Weight.Normal, "JetBrains Mono")
        self.f_chip = font(9.3, QFont.Weight.DemiBold)
        self.f_pill = font(10.2, QFont.Weight.DemiBold)
        self.f_service = font(11.7, QFont.Weight.DemiBold)
        self.f_small = font(9.8, QFont.Weight.Medium)
        self.tree.viewport().update()

    # -- sizing --------------------------------------------------------------
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        if index.parent().isValid():
            return QSize(option.rect.width(), 44)
        return QSize(option.rect.width(), 64)

    # -- painting ------------------------------------------------------------
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        device: Device | None = index.data(ROLE_DEVICE)
        service_data = index.data(ROLE_SERVICE)
        is_child = index.parent().isValid()
        row_rect = QRect(0, option.rect.top(), self.tree.viewport().width(), option.rect.height())

        if index.column() == 0:
            self._paint_row_bg(painter, option, row_rect, is_child)

        if is_child:
            if not isinstance(service_data, dict):
                painter.restore()
                return
            service = Service.from_dict(service_data)
            self._paint_service(painter, option, index, row_rect, service)
        elif device is not None:
            self._paint_device(painter, option, index, row_rect, device)
        painter.restore()

    def _paint_row_bg(self, painter: QPainter, option: QStyleOptionViewItem, row_rect: QRect,
                      is_child: bool) -> None:
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = self.tree.hovered_row == option.rect.top()
        bg = QRectF(row_rect.adjusted(4, 2, -4, -2))
        if selected:
            sel = QColor(P.accent); sel.setAlpha(24)
            sel_border = QColor(P.accent); sel_border.setAlpha(48)
            painter.setBrush(sel)
            painter.setPen(QPen(sel_border, 1))
            painter.drawRoundedRect(bg, 10, 10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(P.accent))
            painter.drawRoundedRect(QRectF(7, bg.top() + (bg.height() - 22) / 2, 3, 22), 1.5, 1.5)
        elif hovered:
            hover = QColor(P.hover_rgb); hover.setAlpha(9)
            painter.setBrush(hover)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bg, 10, 10)
        if is_child:
            painter.setPen(QPen(QColor(P.border_soft), 1))
            x = option.rect.left() + 19
            painter.drawLine(QPoint(x, row_rect.top()), QPoint(x, row_rect.bottom()))

    def _paint_device(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex,
                      row_rect: QRect, device: Device) -> None:
        rect = option.rect
        col = index.column()
        base_y = row_rect.top()

        if col == COL_DEVICE:
            # chevron
            if device.services:
                expanded = self.tree.isExpanded(index)
                painter.drawPixmap(
                    QRect(12, base_y + (row_rect.height() - 14) // 2, 14, 14),
                    pixmap("chevron-down" if expanded else "chevron-right", P.dim, 14),
                )
            color = kind_color(device.kind)
            tile = QRectF(34, base_y + 15, 34, 34)
            grad = QLinearGradient(tile.topLeft(), tile.bottomRight())
            top = QColor(color)
            top.setAlpha(46)
            bottom = QColor(color)
            bottom.setAlpha(18)
            grad.setColorAt(0, top)
            grad.setColorAt(1, bottom)
            painter.setBrush(grad)
            border = QColor(color)
            border.setAlpha(75)
            painter.setPen(QPen(border, 1))
            painter.drawRoundedRect(tile, 10, 10)
            icon_name = {
                "router": "router", "computer": "monitor", "server": "server", "printer": "printer",
                "phone": "smartphone", "tablet": "tablet", "tv": "tv", "camera": "camera",
                "nas": "hard-drive", "iot": "cpu", "unknown": "device",
            }.get(device.kind, "device")
            painter.drawPixmap(QRect(42, base_y + 23, 18, 18), pixmap(icon_name, QColor(color).lighter(140).name(), 18))

            text_x = 78
            text_w = rect.width() - text_x - 26
            name = device.title or tr("Без имени")
            painter.setFont(self.f_name)
            painter.setPen(QColor(P.text if device.is_online() else P.text_soft if device.title else P.dim))
            if not device.title:
                painter.setPen(QColor(P.dim))
            fm = QFontMetrics(self.f_name)
            painter.drawText(
                QRect(text_x, base_y + 13, text_w, 19),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                fm.elidedText(name, Qt.TextElideMode.ElideRight, text_w),
            )
            # favorite star
            star_x = rect.right() - 16
            if device.favorite:
                painter.drawPixmap(QRect(star_x, base_y + 8, 12, 12), pixmap("star-fill", P.amber, 12))

            subtitle_bits = [device.kind_label]
            if device.os_label and device.os_name not in ("Сетевая ОС",):
                subtitle_bits.append(device.os_label)
            if device.vendor:
                subtitle_bits.append(device.vendor)
            subtitle = " · ".join(subtitle_bits)
            painter.setFont(self.f_sub)
            painter.setPen(QColor(P.muted if device.is_online() else P.dim))
            fm2 = QFontMetrics(self.f_sub)
            painter.drawText(
                QRect(text_x, base_y + 33, text_w, 16),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                fm2.elidedText(subtitle, Qt.TextElideMode.ElideRight, text_w),
            )

        elif col == COL_IP:
            painter.setFont(self.f_ip)
            painter.setPen(QColor(P.text_soft if device.is_online() else P.dim))
            painter.drawText(
                rect.adjusted(10, 0, -4, 0),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                device.ip,
            )
        elif col == COL_MAC:
            painter.setFont(self.f_mac)
            painter.setPen(QColor(P.muted if device.mac else P.dim))
            painter.drawText(
                rect.adjusted(10, 0, -4, 0),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                device.mac or "—",
            )
        elif col == COL_STATUS:
            self._paint_status(painter, rect, device)
        elif col == COL_SERVICES:
            self._paint_chips(painter, rect, device)

    def _paint_status(self, painter: QPainter, rect: QRect, device: Device) -> None:
        color = P.green if device.is_online() else (P.red if device.status == "offline" else P.dim)
        text = device.status_label if device.is_online() else tr("Не в сети" if device.status == "offline" else "Неизвестно")
        fm = QFontMetrics(self.f_pill)
        width = fm.horizontalAdvance(text) + 28
        pill = QRectF(rect.left() + 10, rect.center().y() - 11, width, 22)
        c = QColor(color)
        bg = QColor(c)
        bg.setAlpha(20)
        border = QColor(c)
        border.setAlpha(58)
        painter.setBrush(bg)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(pill, 11, 11)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(pill.left() + 10, rect.center().y()), 2.8, 2.8)
        painter.setFont(self.f_pill)
        painter.setPen(c.darker(112) if P.mode == "light" else c.lighter(112))
        painter.drawText(
            QRectF(pill.left() + 17, pill.top(), pill.width() - 20, pill.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            text,
        )

    def _paint_chips(self, painter: QPainter, rect: QRect, device: Device) -> None:
        if not device.services:
            painter.setFont(self.f_small)
            painter.setPen(QColor(P.dim))
            painter.drawText(rect.adjusted(10, 0, -4, 0),
                             int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), "—")
            return
        x = rect.left() + 10
        max_x = rect.right() - 6
        shown = 0
        for service in sorted(device.services, key=lambda s: s.port):
            label = SERVICE_SHORT.get(service.kind, service.name[:6])
            fm = QFontMetrics(self.f_chip)
            width = fm.horizontalAdvance(label) + 12
            if x + width > max_x:
                break
            if shown >= 2:
                break
            color = service_color(service.kind)
            chip = QRectF(x, rect.center().y() - 9, width, 18)
            c = QColor(color)
            bg = QColor(c)
            bg.setAlpha(20)
            border = QColor(c)
            border.setAlpha(48)
            painter.setBrush(bg)
            painter.setPen(QPen(border, 1))
            painter.drawRoundedRect(chip, 6, 6)
            painter.setFont(self.f_chip)
            painter.setPen(c.darker(112) if P.mode == "light" else c.lighter(120))
            painter.drawText(chip, int(Qt.AlignmentFlag.AlignCenter), label)
            x += width + 4
            shown += 1
        remaining = len(device.services) - shown
        if remaining > 0:
            label = f"+{remaining}"
            fm = QFontMetrics(self.f_chip)
            width = fm.horizontalAdvance(label) + 10
            if x + width <= max_x:
                remaining_bg = QColor(P.hover_rgb); remaining_bg.setAlpha(14)
                painter.setBrush(remaining_bg)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRectF(x, rect.center().y() - 9, width, 18), 6, 6)
                painter.setFont(self.f_chip)
                painter.setPen(QColor(P.muted))
                painter.drawText(QRectF(x, rect.center().y() - 9, width, 18),
                                 int(Qt.AlignmentFlag.AlignCenter), label)

    def _paint_service(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex,
                       row_rect: QRect, service: Service) -> None:
        rect = option.rect
        col = index.column()
        color = service_color(service.kind)
        if col == COL_DEVICE:
            tile = QRectF(rect.left() + 30, row_rect.top() + 10, 24, 24)
            c = QColor(color)
            c.setAlpha(28)
            painter.setBrush(c)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(tile, 7, 7)
            icon_name = {
                "http": "globe", "https": "globe", "smb": "folder", "ftp": "folder",
                "ssh": "terminal", "telnet": "terminal", "rdp": "monitor", "vnc": "monitor",
                "printer": "printer", "ipp": "printer", "lpd": "printer",
                "rtsp": "camera", "afp": "folder", "iphone": "smartphone",
            }.get(service.kind, "signal")
            painter.drawPixmap(QRect(rect.left() + 35, row_rect.top() + 15, 14, 14),
                               pixmap(icon_name, color, 14))
            text_x = rect.left() + 62
            text_w = rect.width() - 62
            painter.setFont(self.f_service)
            painter.setPen(QColor(P.text_soft))
            painter.drawText(
                QRect(text_x, row_rect.top() + 7, text_w, 16),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                service.display_name,
            )
            detail = service.product or tr(service.title)
            if detail:
                painter.setFont(self.f_small)
                painter.setPen(QColor(P.dim))
                fm = QFontMetrics(self.f_small)
                painter.drawText(
                    QRect(text_x, row_rect.top() + 22, text_w, 14),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                    fm.elidedText(detail, Qt.TextElideMode.ElideRight, text_w),
                )
        elif col == COL_IP:
            painter.setFont(self.f_small)
            painter.setPen(QColor(P.dim))
            painter.drawText(rect.adjusted(10, 0, -4, 0),
                             int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                             f"{tr('порт')} {service.port}")
        elif col == COL_SERVICES:
            button = QRectF(rect.right() - 94, row_rect.center().y() - 13, 84, 26)
            grad = QLinearGradient(button.topLeft(), button.bottomRight())
            grad.setColorAt(0.0, QColor(P.accent))
            grad.setColorAt(0.55, QColor(P.logo2))
            grad.setColorAt(1.0, QColor(P.accent2))
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(button, 8, 8)
            painter.setFont(font(9.6, QFont.Weight.DemiBold))
            painter.setPen(QColor(P.primary_text))
            painter.drawText(
                QRectF(button.left() + 10, button.top(), 52, button.height()),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                tr("Открыть"),
            )
            painter.drawPixmap(
                QRect(int(button.right()) - 20, int(button.top()) + 7, 12, 12),
                pixmap("arrow-up-right", P.primary_text, 12),
            )


class DeviceTree(QTreeView):
    device_selected = pyqtSignal(object)
    device_activated = pyqtSignal(object)
    service_activated = pyqtSignal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.hovered_row = -1
        self._last_service_key: tuple[str, int] | None = None
        self._last_service_time = 0.0
        self.setRootIsDecorated(False)
        self.setIndentation(26)
        self.setUniformRowHeights(False)
        self.setAllColumnsShowFocus(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setExpandsOnDoubleClick(False)
        self.setAnimated(False)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHeader(HeaderView(self))
        self.header().setSortIndicatorShown(True)
        self.header().setStretchLastSection(False)
        self.setItemDelegate(DeviceDelegate(self))

    def set_model(self, model) -> None:
        self.setModel(model)
        self.setSortingEnabled(True)
        self.header().setSortIndicator(COL_IP, Qt.SortOrder.AscendingOrder)
        self.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.header().resizeSection(COL_IP, 122)
        self.header().resizeSection(COL_MAC, 148)
        self.header().resizeSection(COL_STATUS, 100)
        self.header().resizeSection(COL_SERVICES, 156)
        self.sortByColumn(COL_IP, Qt.SortOrder.AscendingOrder)
        self.doubleClicked.connect(self._on_double_click)
        if self.selectionModel() is not None:
            self.selectionModel().selectionChanged.connect(self._on_selection)
        self.verticalScrollBar().rangeChanged.connect(lambda *_: self._fit_columns())
        QTimer.singleShot(0, self._fit_columns)

    def _fit_columns(self) -> None:
        header = self.header()
        if header is None or header.count() < 5:
            return
        available = self.viewport().width()
        if available <= 0:
            return
        fixed_sizes = {COL_IP: 122, COL_MAC: 148, COL_STATUS: 100, COL_SERVICES: 156}
        for column, size in fixed_sizes.items():
            header.resizeSection(column, size)
        header.resizeSection(COL_DEVICE, max(180, available - sum(fixed_sizes.values())))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_columns()

    def selected_devices(self) -> list[Device]:
        result: list[Device] = []
        selection = self.selectionModel()
        if not selection:
            return result
        seen = set()
        for index in selection.selectedIndexes():
            top = index.parent() if index.parent().isValid() else index
            device = top.data(ROLE_DEVICE)
            if isinstance(device, Device) and device.ip not in seen:
                seen.add(device.ip)
                result.append(device)
        return result

    def _on_selection(self, selected, deselected) -> None:
        devices = self.selected_devices()
        self.device_selected.emit(devices[0] if devices else None)

    def _emit_service(self, device: Device, service: Service) -> None:
        key = (device.ip, service.port)
        now = time.monotonic()
        if key == self._last_service_key and now - self._last_service_time < 0.8:
            return
        self._last_service_key = key
        self._last_service_time = now
        self.service_activated.emit(device, service)

    def _on_double_click(self, index: QModelIndex) -> None:
        if index.parent().isValid():
            service_data = index.sibling(index.row(), 0).data(ROLE_SERVICE)
            device = index.parent().data(ROLE_DEVICE)
            if isinstance(service_data, dict) and isinstance(device, Device):
                self._emit_service(device, Service.from_dict(service_data))
            return
        device = index.data(ROLE_DEVICE)
        if isinstance(device, Device):
            self.device_activated.emit(device)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.position().toPoint())
            if (index.isValid() and index.parent().isValid()
                    and index.column() == COL_SERVICES):
                rect = self.visualRect(index)
                button = QRect(rect.right() - 94, rect.top() + (rect.height() - 26) // 2, 84, 26)
                if button.contains(event.position().toPoint()):
                    service_data = index.sibling(index.row(), 0).data(ROLE_SERVICE)
                    device = index.parent().data(ROLE_DEVICE)
                    if isinstance(service_data, dict) and isinstance(device, Device):
                        self.setCurrentIndex(index)
                        self._emit_service(device, Service.from_dict(service_data))
                    event.accept()
                    return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and not index.parent().isValid() and event.button() == Qt.MouseButton.LeftButton:
            rect = self.visualRect(index)
            if event.position().x() - rect.left() <= 30 and index.model().rowCount(index) > 0:
                self.setExpanded(index, not self.isExpanded(index))
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        index = self.indexAt(event.position().toPoint())
        row = self.visualRect(index).top() if index.isValid() else -1
        if row != self.hovered_row:
            self.hovered_row = row
            self.viewport().update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self.hovered_row != -1:
            self.hovered_row = -1
            self.viewport().update()
        super().leaveEvent(event)
