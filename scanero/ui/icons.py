"""Scanero icon factory (tinted PNG masks, no QtSvg dependency)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


@lru_cache(maxsize=1024)
def pixmap(name: str, color: str, size: int = 20, dpr: int = 2) -> QPixmap:
    target = QPixmap(max(1, int(size * dpr)), max(1, int(size * dpr)))
    target.fill(Qt.GlobalColor.transparent)
    path = ICON_DIR / f"{name}.png"
    base = QPixmap(str(path)) if path.exists() else QPixmap()
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    if not base.isNull():
        painter.drawPixmap(QRect(0, 0, target.width(), target.height()), base)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(target.rect(), QColor(color))
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(target.rect().adjusted(3, 3, -3, -3))
    painter.end()
    target.setDevicePixelRatio(dpr)
    return target


def icon(name: str, color: str, size: int = 20, dpr: int = 2) -> QIcon:
    return QIcon(pixmap(name, color, size, dpr))


def scaled_pixmap(name: str, color: str, size: int, dpr: int = 2) -> QPixmap:
    return pixmap(name, color, size, dpr)
