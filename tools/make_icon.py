#!/usr/bin/env python3
"""Render the Scanero application icon to PNG."""
from __future__ import annotations

import math
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication

OUT = Path(__file__).resolve().parent.parent / "scanero" / "assets" / "scanero.png"


def draw(size: int) -> None:
    app = QApplication.instance() or QApplication([])
    from PyQt6.QtGui import QPixmap

    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = QRectF(4, 4, size - 8, size - 8)
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0.0, QColor("#2BE0F5"))
    grad.setColorAt(0.55, QColor("#4FA8FF"))
    grad.setColorAt(1.0, QColor("#8B8CFF"))
    path = QPainterPath()
    path.addRoundedRect(rect, size * 0.26, size * 0.26)
    p.fillPath(path, grad)

    cx, cy = size / 2, size / 2
    r = size * 0.27
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(7, 14, 25, 150), max(2.0, size / 34)))
    p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
    p.setPen(QPen(QColor(7, 14, 25, 210), max(3.0, size / 24)))
    p.drawLine(QPointF(cx, cy), QPointF(cx + r * 0.72, cy - r * 0.72))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(7, 14, 25, 220))
    p.drawEllipse(QRectF(cx + r * 0.72 - size * 0.035, cy - r * 0.72 - size * 0.035, size * 0.07, size * 0.07))
    p.end()
    pm.save(str(OUT))
    print("saved", OUT)


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    draw(256)
