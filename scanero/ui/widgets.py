"""Custom painted widgets used across the Scanero IP scanner UI."""
from __future__ import annotations

import math
import time
from typing import Iterable

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QConicalGradient,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.models import Device, Service
from ..i18n import current_language, tr, translate_text
from .icons import icon, pixmap
from .theme import P, kind_color, rgba, service_color, sp


def base_font(size: float, weight: QFont.Weight = QFont.Weight.Normal,
              family: str = "Inter") -> QFont:
    f = QFont(family)
    f.setPixelSize(int(round(size)))
    f.setWeight(weight)
    return f


def font(size: float, weight: QFont.Weight = QFont.Weight.Normal, family: str = "Inter") -> QFont:
    """A font scaled by the user's interface font-size preference."""
    f = QFont(family)
    f.setPixelSize(sp(size))
    f.setWeight(weight)
    return f


def set_widget_font(widget: QWidget, base: QFont) -> None:
    """Store an unscaled font on a widget and apply it at the current scale."""
    widget.setProperty("scaneroBaseFont", QFont(base))
    scaled = QFont(base)
    if scaled.pixelSize() > 0:
        scaled.setPixelSize(sp(scaled.pixelSize()))
    widget.setFont(scaled)


def refresh_widget_fonts(root: QWidget) -> None:
    widgets = [root] + root.findChildren(QWidget)
    for widget in widgets:
        stored = widget.property("scaneroBaseFont")
        if isinstance(stored, QFont):
            set_widget_font(widget, stored)


_EN_PLURALS = {
    ("адрес", "адреса", "адресов"): ("address", "addresses"),
    ("устройство", "устройства", "устройств"): ("device", "devices"),
    ("сервис", "сервиса", "сервисов"): ("service", "services"),
    ("порт", "порта", "портов"): ("port", "ports"),
}


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(int(n))
    if current_language() == "en":
        en = _EN_PLURALS.get((one, few, many))
        if en:
            return en[0] if n == 1 else en[1]
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def hline() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


class LogoWidget(QWidget):
    def __init__(self, size: int = 32, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1, 1, self._size - 2, self._size - 2)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(P.logo1))
        grad.setColorAt(0.55, QColor(P.logo2))
        grad.setColorAt(1.0, QColor(P.logo3))
        path = QPainterPath()
        path.addRoundedRect(rect, self._size * 0.3, self._size * 0.3)
        p.fillPath(path, grad)
        p.setPen(QPen(QColor(P.primary_text), max(1.0, self._size / 26)))
        cx, cy = self._size / 2, self._size / 2
        r = self._size * 0.28
        p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        p.setPen(QPen(QColor(P.primary_text), max(1.2, self._size / 20)))
        p.drawLine(QPointF(cx, cy), QPointF(cx + r * 0.72, cy - r * 0.72))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(P.primary_text))
        p.drawEllipse(QPointF(cx + r * 0.72, cy - r * 0.72), self._size * 0.035, self._size * 0.035)


class IconButton(QPushButton):
    def __init__(
        self,
        icon_name: str,
        size: int = 20,
        color: str = P.muted,
        parent: QWidget | None = None,
        tooltip: str = "",
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_size = size
        self._color = color
        self.setProperty("variant", "icon")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(size + 14, size + 14)
        self.setIcon(icon(icon_name, color, size))
        self.setIconSize(QSize(size, size))
        if tooltip:
            self.setToolTip(tooltip)

    def set_color(self, color: str) -> None:
        self._color = color
        self.setIcon(icon(self._icon_name, color, self._icon_size))


class NavButton(QAbstractButton):
    def __init__(self, icon_name: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._text = text
        self._badge = ""
        self._active = False
        self._hover = 0.0
        self.setCheckable(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._anim = QVariantAnimation(self, duration=140)
        self._anim.valueChanged.connect(self._on_hover)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _on_hover(self, value) -> None:
        try:
            self._hover = float(value)
        except Exception:
            self._hover = 0.0
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(event)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def set_badge(self, text: str) -> None:
        self._badge = text
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, 44)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        if self._active:
            bg = QColor(P.accent)
            bg.setAlpha(18)
            p.setBrush(bg)
            p.setPen(QPen(QColor(34, 211, 238, 40), 1))
            p.drawRoundedRect(rect.adjusted(4, 2, -4, -2), 11, 11)
        elif self._hover > 0:
            bg = QColor(P.hover_rgb)
            bg.setAlpha(int(9 * self._hover))
            p.setBrush(bg)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(rect.adjusted(4, 2, -4, -2), 11, 11)

        if self._active:
            accent = QColor(P.accent)
            p.setBrush(accent)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(0, 13, 3, 18), 1.5, 1.5)

        color = P.accent if self._active else (P.text_soft if self._hover > 0.5 else P.muted)
        icon_px = pixmap(self._icon_name, color, 19)
        p.drawPixmap(QRect(20, 12, 20, 20), icon_px)

        p.setFont(font(13, QFont.Weight.DemiBold if self._active else QFont.Weight.Medium))
        p.setPen(QColor(P.text if self._active else (P.text_soft if self._hover > 0.4 else P.muted)))
        p.drawText(QRect(50, 0, self.width() - 90, self.height()), Qt.AlignmentFlag.AlignVCenter, tr(self._text))

        if self._badge:
            fm = QFontMetrics(font(10.5, QFont.Weight.DemiBold))
            bw = max(22, fm.horizontalAdvance(self._badge) + 12)
            br = QRectF(self.width() - bw - 16, 13, bw, 18)
            bg = QColor(P.accent if self._active else P.badge_bg)
            bg.setAlpha(40 if self._active else 160)
            p.setBrush(bg)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(br, 9, 9)
            p.setFont(font(10.5, QFont.Weight.DemiBold))
            p.setPen(QColor(P.accent if self._active else P.text_soft))
            p.drawText(br, Qt.AlignmentFlag.AlignCenter, self._badge)


class NetworkCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._iface = None
        self._hover = False
        self.setFixedHeight(98)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Выбрать сетевой интерфейс")

    def set_interface(self, iface) -> None:
        self._iface = iface
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        bg = QColor(P.card)
        bg.setAlpha(240 if self._hover else 220)
        p.setBrush(bg)
        p.setPen(QPen(QColor(P.border_hover if self._hover else P.border_soft), 1))
        p.drawRoundedRect(rect, 14, 14)

        # Icon tile
        tile = QRectF(14, 16, 34, 34)
        grad = QLinearGradient(tile.topLeft(), tile.bottomRight())
        c1 = QColor(P.accent); c1.setAlpha(45)
        c2 = QColor(P.accent2); c2.setAlpha(28)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        p.setBrush(grad)
        border = QColor(P.accent); border.setAlpha(60)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(tile, 10, 10)
        iface = self._iface
        icon_name = "wifi" if (iface and iface.wireless) else "ethernet"
        p.drawPixmap(QRect(22, 24, 18, 18), pixmap(icon_name, P.accent, 18))

        p.setFont(font(10, QFont.Weight.DemiBold))
        p.setPen(QColor(P.dim))
        p.drawText(QRectF(58, 12, self.width() - 70, 14), Qt.AlignmentFlag.AlignLeft, tr("ТЕКУЩАЯ СЕТЬ"))

        p.setFont(font(13, QFont.Weight.DemiBold))
        p.setPen(QColor(P.text))
        title = iface.ssid if (iface and iface.ssid) else (tr(iface.title) if iface else tr("Сеть не найдена"))
        title = QFontMetrics(p.font()).elidedText(title, Qt.TextElideMode.ElideRight, int(self.width() - 76))
        p.drawText(QRectF(58, 26, self.width() - 70, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        p.setFont(font(11, QFont.Weight.Medium, "JetBrains Mono"))
        p.setPen(QColor(P.muted))
        subtitle = (f"{iface.ip}/{iface.prefix}" if iface else tr("нет подключения"))
        p.drawText(QRectF(58, 46, self.width() - 70, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle)

        dot = QPointF(22, 78)
        p.setPen(Qt.PenStyle.NoPen)
        glow = QColor(P.green); glow.setAlpha(50)
        p.setBrush(glow)
        p.drawEllipse(dot, 7, 7)
        p.setBrush(QColor(P.green))
        p.drawEllipse(dot, 3.2, 3.2)
        p.setFont(font(10.5, QFont.Weight.Medium))
        p.setPen(QColor(P.dim))
        p.drawText(QRectF(34, 68, self.width() - 50, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   tr("Подключено") if iface else tr("Недоступно"))


class StatCard(QWidget):
    def __init__(self, title: str, icon_name: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._icon_name = icon_name
        self._color = color
        self._value = 0
        self._target = 0
        self._hint = ""
        self._display = "0"
        self._hover = False
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._anim = QVariantAnimation(self, duration=620)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, value) -> None:
        self._display = str(int(value))
        self.update()

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def set_value(self, value: int | str, hint: str = "", animate: bool = True) -> None:
        if isinstance(value, str):
            self._anim.stop()
            self._display = value
            self._target = 0
            self._value = 0
            self._hint = hint
            self.update()
            return
        self._hint = hint
        self._target = int(value)
        if not animate:
            self._anim.stop()
            self._value = self._target
            self._display = str(self._target)
            self.update()
            return
        self._anim.stop()
        try:
            self._anim.setStartValue(int(self._display) if self._display.isdigit() else 0)
        except Exception:
            self._anim.setStartValue(0)
        self._anim.setEndValue(self._target)
        self._anim.start()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        bg = QColor(P.card_hover if self._hover else P.card)
        bg.setAlpha(250 if self._hover else 235)
        p.setBrush(bg)
        p.setPen(QPen(QColor(P.border_hover if self._hover else P.border_soft), 1))
        p.drawRoundedRect(rect, 15, 15)

        tile = QRectF(self.width() - 48, 14, 32, 32)
        c = QColor(self._color)
        c.setAlpha(26)
        p.setBrush(c)
        p.setPen(QPen(QColor(self._color).lighter(100), 1))
        pen = QPen(QColor(self._color))
        pen.setColor(QColor(self._color))
        pen.setWidthF(1)
        p.setPen(pen)
        p.drawRoundedRect(tile, 9, 9)
        p.drawPixmap(QRect(int(tile.x()) + 7, int(tile.y()) + 7, 18, 18), pixmap(self._icon_name, self._color, 18))

        p.setFont(font(9.8, QFont.Weight.DemiBold))
        p.setPen(QColor(P.dim))
        p.drawText(QRectF(16, 15, self.width() - 70, 14), Qt.AlignmentFlag.AlignLeft, tr(self._title).upper())

        p.setFont(font(26, QFont.Weight.DemiBold))
        p.setPen(QColor(P.text))
        p.drawText(
            QRectF(15, 34, self.width() - 30, 32),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            tr(self._display),
        )

        if self._hint:
            p.setFont(font(10.5, QFont.Weight.Medium))
            p.setPen(QColor(P.muted))
            p.drawText(QRectF(16, 67, self.width() - 30, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tr(self._hint))


class Avatar(QWidget):
    def __init__(self, size: int = 58, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self._kind = "unknown"
        self._online = False
        self.setFixedSize(size, size)

    def set_device(self, device: Device | None) -> None:
        self._kind = device.kind if device else "unknown"
        self._online = bool(device and device.is_online())
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1, 1, self._size - 2, self._size - 2)
        color = QColor(kind_color(self._kind))
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        top = QColor(color)
        top.setAlpha(78)
        bottom = QColor(color)
        bottom.setAlpha(24)
        grad.setColorAt(0, top)
        grad.setColorAt(1, bottom)
        p.setBrush(grad)
        border = QColor(color)
        border.setAlpha(110)
        p.setPen(QPen(border, 1.2))
        p.drawRoundedRect(rect, self._size * 0.31, self._size * 0.31)
        icon_name = {
            "router": "router", "computer": "monitor", "server": "server", "printer": "printer",
            "phone": "smartphone", "tablet": "tablet", "tv": "tv", "camera": "camera",
            "nas": "hard-drive", "iot": "cpu", "unknown": "device",
        }.get(self._kind, "device")
        isize = int(self._size * 0.44)
        p.drawPixmap(
            QRect((self._size - isize) // 2, (self._size - isize) // 2, isize, isize),
            pixmap(icon_name, color.lighter(135).name(), isize),
        )
        if self._online:
            dot = QPointF(self._size - 10, self._size - 10)
            p.setPen(QPen(QColor(P.card), 3))
            p.setBrush(QColor(P.green))
            p.drawEllipse(dot, 5, 5)


class StatusPill(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = "В сети"
        self._color = P.green
        self.setFixedHeight(24)

    def set_status(self, status: str) -> None:
        if status == "online":
            self._text, self._color = "В сети", P.green
        elif status == "offline":
            self._text, self._color = "Не в сети", P.red
        else:
            self._text, self._color = "Неизвестно", P.dim
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = QFontMetrics(font(10.5, QFont.Weight.DemiBold))
        return QSize(fm.horizontalAdvance(self._text) + 34, 24)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(self._color)
        bg = QColor(c)
        bg.setAlpha(22)
        p.setBrush(bg)
        border = QColor(c)
        border.setAlpha(60)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 12, 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawEllipse(QPointF(12, self.height() / 2), 3.1, 3.1)
        p.setFont(font(10.5, QFont.Weight.DemiBold))
        p.setPen(c.darker(112) if P.mode == "light" else c.lighter(115))
        p.drawText(QRectF(20, 0, self.width() - 24, self.height()), Qt.AlignmentFlag.AlignVCenter, tr(self._text))


class ToggleSwitch(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)
        self._pos = 0.0
        self._anim = QVariantAnimation(self, duration=160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_pos)
        self.toggled.connect(self._animate)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def _on_pos(self, value) -> None:
        try:
            self._pos = float(value)
        except Exception:
            self._pos = 0.0
        self.update()

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        self._pos = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        off = QColor(P.toggle_off)
        on = QColor(P.accent)
        mix = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        p.setBrush(mix)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(track, 12, 12)
        knob_x = 3 + (self.width() - 27) * self._pos
        p.setBrush(QColor(P.knob))
        p.drawEllipse(QRectF(knob_x, 3, 18, 18))


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Поиск по имени, IP, MAC…", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.setMinimumHeight(38)
        self.addAction(icon("search", P.dim, 16), QLineEdit.ActionPosition.LeadingPosition)


class RadarWidget(QWidget):
    def __init__(self, size: int = 200, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._devices: list[Device] = []
        self._angle = 0.0
        self._pulse = 0.0
        self.setMinimumSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        if not self.isVisible():
            return
        self._angle = (self._angle + 2.6) % 360
        self._pulse += 0.07
        self.update()

    def set_devices(self, devices: Iterable[Device]) -> None:
        self._devices = [d for d in devices if d.is_online()][:160]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        cx, cy = self.width() / 2, self.height() / 2
        maxr = side / 2 - 8

        # soft radial backdrop
        bg = QRadialGradient(QPointF(cx, cy), maxr * 1.2)
        a1 = QColor(P.glow1); a1.setAlpha(16)
        a2 = QColor(P.glow2); a2.setAlpha(7)
        bg.setColorAt(0, a1)
        bg.setColorAt(0.65, a2)
        bg.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(bg)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), maxr * 1.12, maxr * 1.12)

        for i in range(4):
            r = maxr * (0.26 + i * 0.245)
            grid = QColor(P.grid); grid.setAlpha(46 if i < 3 else 70)
            pen = QPen(grid)
            pen.setWidthF(1.0)
            if i == 0:
                pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)

        p.setPen(QPen(QColor(P.grid), 1))
        p.drawLine(QPointF(cx - maxr, cy), QPointF(cx + maxr, cy))
        p.drawLine(QPointF(cx, cy - maxr), QPointF(cx, cy + maxr))

        # ticks
        for deg in range(0, 360, 10):
            a = math.radians(deg)
            r1 = maxr
            r2 = maxr - (6 if deg % 30 == 0 else 3)
            p.setPen(QPen(QColor(P.grid), 1))
            p.drawLine(
                QPointF(cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
                QPointF(cx + r2 * math.cos(a), cy + r2 * math.sin(a)),
            )

        # sweep
        sweep = QRectF(cx - maxr, cy - maxr, maxr * 2, maxr * 2)
        grad = QConicalGradient(QPointF(cx, cy), -self._angle)
        c0 = QColor(P.accent); c0.setAlpha(96)
        c1 = QColor(P.accent); c1.setAlpha(0)
        grad.setColorAt(0.0, c0)
        mid = QColor(P.accent); mid.setAlpha(38)
        grad.setColorAt(0.1, mid)
        grad.setColorAt(0.19, c1)
        grad.setColorAt(1.0, c1)
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPie(sweep, int(-self._angle * 16), int(64 * 16))

        line_end = QPointF(cx + maxr * math.cos(math.radians(-self._angle)),
                           cy + maxr * math.sin(math.radians(-self._angle)))
        sweep_color = QColor(P.accent); sweep_color.setAlpha(170)
        p.setPen(QPen(sweep_color, 1.4))
        p.drawLine(QPointF(cx, cy), line_end)

        # blips
        for idx, device in enumerate(self._devices):
            try:
                last = int(device.ip.split(".")[-1])
            except Exception:
                last = idx * 17
            angle = math.radians((last * 47 + idx * 11) % 360)
            radius = maxr * (0.22 + ((last * 13) % 70) / 100)
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            color = QColor(kind_color(device.kind))
            pulse = 0.5 + 0.5 * math.sin(self._pulse + idx)
            glow = QColor(color)
            glow.setAlpha(int(30 + 30 * pulse))
            p.setBrush(glow)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x, y), 6 + pulse * 3, 6 + pulse * 3)
            p.setBrush(color)
            p.drawEllipse(QPointF(x, y), 2.6, 2.6)

        # center
        p.setPen(Qt.PenStyle.NoPen)
        center_glow = QColor(P.accent); center_glow.setAlpha(55)
        p.setBrush(center_glow)
        p.drawEllipse(QPointF(cx, cy), 7, 7)
        p.setBrush(QColor(P.accent))
        p.drawEllipse(QPointF(cx, cy), 3, 3)


class ProgressBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self.setFixedHeight(6)
        self.setMinimumWidth(120)
        self._anim = QVariantAnimation(self, duration=240)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_value)

    def _on_value(self, value) -> None:
        try:
            self._value = max(0.0, min(100.0, float(value)))
        except Exception:
            self._value = 0.0
        self.update()

    def set_value(self, value: float, animate: bool = True) -> None:
        value = max(0.0, min(100.0, float(value)))
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._value)
            self._anim.setEndValue(value)
            self._anim.start()
        else:
            self._value = value
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0, 0, self.width(), self.height())
        p.setBrush(QColor(P.track))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(track, self.height() / 2, self.height() / 2)
        if self._value > 0:
            fill = QRectF(0, 0, max(6.0, self.width() * self._value / 100), self.height())
            grad = QLinearGradient(fill.topLeft(), fill.topRight())
            grad.setColorAt(0, QColor(P.accent))
            grad.setColorAt(1, QColor(P.accent2))
            p.setBrush(grad)
            p.drawRoundedRect(fill, self.height() / 2, self.height() / 2)


class EmptyState(QWidget):
    scan_clicked = pyqtSignal()
    reset_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 26)
        layout.setSpacing(6)
        layout.addStretch(1)
        self.radar = RadarWidget(190, self)
        layout.addWidget(self.radar, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(12)
        self.title = QLabel("Готовы к сканированию", self)
        set_widget_font(self.title, base_font(19, QFont.Weight.DemiBold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        self.subtitle = QLabel("", self)
        set_widget_font(self.subtitle, base_font(12.5))
        self.subtitle.setStyleSheet(f"color: {P.muted};")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle)
        layout.addSpacing(10)
        self.progress = ProgressBar(self)
        self.progress.setFixedWidth(280)
        self.progress.setVisible(False)
        layout.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        self.scan_btn = QPushButton("Сканировать", self)
        self.scan_btn.setProperty("variant", "primary")
        self.scan_btn.setIcon(icon("scan", P.primary_text, 17))
        self.scan_btn.setIconSize(QSize(17, 17))
        self.scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_btn.clicked.connect(self.scan_clicked.emit)
        self.reset_btn = QPushButton("Сбросить фильтры", self)
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.clicked.connect(self.reset_clicked.emit)
        self.reset_btn.setVisible(False)
        self.settings_btn = QPushButton("Настроить диапазон", self)
        self.settings_btn.setProperty("variant", "ghost")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        row.addWidget(self.reset_btn)
        row.addWidget(self.settings_btn)
        row.addWidget(self.scan_btn)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)
        self._mode = "idle"

    def set_devices(self, devices: Iterable[Device]) -> None:
        self.radar.set_devices(devices)

    def refresh_theme(self) -> None:
        self.subtitle.setStyleSheet(f"color: {P.muted};")
        self.reset_btn.setStyleSheet("")
        self.progress.update()
        if self._mode == "scanning":
            self.scan_btn.setIcon(icon("stop", P.primary_text, 14))
        else:
            self.scan_btn.setIcon(icon("scan", P.primary_text, 17))

    def show_idle(self, count: int, range_text: str) -> None:
        self._mode = "idle"
        self.radar.setVisible(True)
        self.progress.setVisible(False)
        self.title.setText("Готовы к сканированию")
        self.subtitle.setText(
            f"Проверим {count} {plural(count, 'адрес', 'адреса', 'адресов')} в сети {range_text}"
            if range_text else "Выберите диапазон и запустите сканирование"
        )
        self.scan_btn.setVisible(True)
        self.reset_btn.setVisible(False)
        self.settings_btn.setVisible(True)
        self.scan_btn.setText("Сканировать")
        self.scan_btn.setIcon(icon("scan", P.primary_text, 17))

    def show_scanning(self) -> None:
        self._mode = "scanning"
        self.radar.setVisible(True)
        self.progress.setVisible(True)
        self.progress.set_value(0, animate=False)
        self.title.setText("Сканируем сеть")
        self.subtitle.setText("Ищем устройства и открытые сервисы…")
        self.scan_btn.setVisible(True)
        self.scan_btn.setText("Остановить")
        self.scan_btn.setIcon(icon("stop", P.primary_text, 14))
        self.reset_btn.setVisible(False)
        self.settings_btn.setVisible(False)

    def set_progress(self, percent: float, text: str) -> None:
        self.progress.set_value(percent)
        self.subtitle.setText(text)

    def show_no_results(self, searching: bool = False) -> None:
        self._mode = "noresults"
        self.radar.setVisible(True)
        self.progress.setVisible(False)
        self.title.setText("Ничего не найдено")
        self.subtitle.setText("Попробуйте изменить фильтр или поисковый запрос" if searching else "В этом диапазоне нет отвечающих устройств")
        self.scan_btn.setVisible(True)
        self.scan_btn.setText("Сканировать снова")
        self.scan_btn.setIcon(icon("refresh", P.primary_text, 16))
        self.reset_btn.setVisible(True)
        self.settings_btn.setVisible(False)


class ServiceChip(QAbstractButton):
    clicked_service = pyqtSignal()

    def __init__(self, service: Service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        detail = service.product or service.title or ""
        tip = f"{service.name} · порт {service.port}" + (f"\n{detail}" if detail else "")
        self.setToolTip(tip)
        self.clicked.connect(self.clicked_service.emit)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        color = service_color(self.service.kind)
        c = QColor(color)
        bg = QColor(c)
        bg.setAlpha(22 if self._hover else 14)
        border = QColor(c)
        border.setAlpha(70 if self._hover else 36)
        p.setBrush(bg)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(rect, 8, 8)
        icon_name = {
            "http": "globe", "https": "globe", "smb": "folder", "ftp": "folder",
            "ssh": "terminal", "telnet": "terminal", "rdp": "monitor", "vnc": "monitor",
            "printer": "printer", "ipp": "printer", "lpd": "printer",
            "rtsp": "camera", "afp": "folder", "iphone": "smartphone",
        }.get(self.service.kind, "signal")
        p.drawPixmap(QRect(9, 9, 16, 16), pixmap(icon_name, color, 16))
        p.setFont(font(10.8, QFont.Weight.DemiBold))
        ink = QColor(color)
        p.setPen(ink.darker(112) if P.mode == "light" else ink.lighter(125))
        fm = QFontMetrics(p.font())
        text = fm.elidedText(tr(self.service.name), Qt.TextElideMode.ElideRight, max(20, self.width() - 37))
        p.drawText(QRectF(31, 0, self.width() - 36, self.height()), Qt.AlignmentFlag.AlignVCenter, text)


class ServiceTile(QAbstractButton):
    clicked_service = pyqtSignal()

    def __init__(self, service: Service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.clicked.connect(self.clicked_service.emit)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setBrush(QColor(P.overlay_hover if self._hover else P.overlay_bg))
        p.setPen(QPen(QColor(P.border_hover if self._hover else P.border_soft), 1))
        p.drawRoundedRect(rect, 10, 10)
        color = service_color(self.service.kind)
        tile = QRectF(9, 9, 30, 30)
        c = QColor(color)
        c.setAlpha(30)
        p.setBrush(c)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(tile, 8, 8)
        icon_name = {
            "http": "globe", "https": "globe", "smb": "folder", "ftp": "folder",
            "ssh": "terminal", "telnet": "terminal", "rdp": "monitor", "vnc": "monitor",
            "printer": "printer", "ipp": "printer", "lpd": "printer",
            "rtsp": "camera", "afp": "folder", "iphone": "smartphone",
        }.get(self.service.kind, "signal")
        p.drawPixmap(QRect(15, 15, 18, 18), pixmap(icon_name, color, 18))
        p.setFont(font(11.5, QFont.Weight.DemiBold))
        p.setPen(QColor(P.text_soft))
        p.drawText(QRectF(48, 6, self.width() - 72, 20), Qt.AlignmentFlag.AlignVCenter,
                   tr(self.service.name))
        p.setFont(font(10))
        p.setPen(QColor(P.dim))
        detail = self.service.product or self.service.title or f"{tr('порт')} {self.service.port}"
        detail = translate_text(detail)
        detail = QFontMetrics(p.font()).elidedText(detail, Qt.TextElideMode.ElideRight, int(self.width() - 76))
        p.drawText(QRectF(48, 24, self.width() - 72, 18), Qt.AlignmentFlag.AlignVCenter, detail)
        p.setPen(QColor(P.dim))
        p.drawPixmap(QRect(self.width() - 26, 16, 14, 14), pixmap("arrow-up-right", P.dim, 14))


class Toast(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setVisible(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)
        self._label = QLabel("", self)
        set_widget_font(self._label, base_font(12.5))
        self._label.setStyleSheet(f"color: {P.text_soft};")
        self._icon = QLabel("", self)
        self._icon.setFixedSize(18, 18)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 10, 17, 10)
        layout.setSpacing(9)
        layout.addWidget(self._icon)
        layout.addWidget(self._label)
        self.setStyleSheet(
            f"QFrame#Toast {{ background: {rgba(P.toast_bg, 0.97)};"
            f" border: 1px solid {P.toast_border}; border-radius: 12px; }}"
        )
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(170)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._hide)

    def refresh_theme(self) -> None:
        self._label.setStyleSheet(f"color: {P.text_soft};")
        self.setStyleSheet(
            f"QFrame#Toast {{ background: {rgba(P.toast_bg, 0.97)};"
            f" border: 1px solid {P.toast_border}; border-radius: 12px; }}"
        )

    def show_message(self, text: str, kind: str = "ok") -> None:
        color = {"ok": P.green, "error": P.red, "info": P.accent}.get(kind, P.accent)
        icon_name = {"ok": "check", "error": "alert", "info": "info"}.get(kind, "info")
        self._icon.setPixmap(pixmap(icon_name, color, 18))
        self._label.setText(text)
        self.adjustSize()
        self._reposition()
        self.setVisible(True)
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(2800)

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent:
            self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 54)

    def _hide(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._after_hide)
        self._anim.start()

    def _after_hide(self) -> None:
        try:
            self._anim.finished.disconnect(self._after_hide)
        except Exception:
            pass
        if self._effect.opacity() <= 0.01:
            self.setVisible(False)


class FitStack(QStackedWidget):
    """QStackedWidget that always resizes the newly shown page to its viewport.

    Without this, a page that was hidden while the window was still being laid
    out keeps its stale (size-hint) geometry and the table ends up narrow.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        super().setCurrentIndex(index)
        self._fit()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._fit()

    def _fit(self) -> None:
        page = self.currentWidget()
        if page is not None:
            page.setGeometry(self.contentsRect())


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full = text

    def setText(self, text: str) -> None:  # noqa: N802
        text = translate_text(text)
        self._full = text
        super().setText(text)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        text = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, self.width())
        p.drawText(self.rect(), int(self.alignment()), text)
