"""Standalone glass-material experiment. Run: python -m ios_restore.ui.glass_lab

This deliberately does not modify iCarcas's production search/download UI.
The background is an original Qt-painted scene; the glass samples and blurs it.
"""
from __future__ import annotations

import math
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QVBoxLayout, QWidget,
)


def blur_image(image: QImage, radius: float = 25.0) -> QImage:
    """Offscreen blur through Qt's graphics effects (no external dependencies)."""
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(image))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    scene.setSceneRect(QRectF(0, 0, image.width(), image.height()))
    result = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    scene.render(painter, QRectF(result.rect()), scene.sceneRect())
    painter.end()
    return result


class GlassLab(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(780, 480)
        self.setMouseTracking(True)
        self._scene = QImage()
        self._blurred = QImage()
        self._hover = False
        self.title = QLabel("Find an app", self)
        self.title.setStyleSheet("color: #122C4A; background: transparent; font-size: 30px; font-weight: 700;")
        self.subtitle = QLabel("A standalone iCarcas material experiment", self)
        self.subtitle.setStyleSheet("color: #365D7D; background: transparent; font-size: 14px;")
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search by name, Store ID or Bundle ID")
        self.search.setStyleSheet(
            "QLineEdit { background: transparent; border: 0; color: #173753; "
            "font-size: 16px; padding: 5px; selection-background-color: #9BDCF0; }"
        )
        self.region = QPushButton("RU  ⌄", self)
        self.region.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,125); border: 1px solid rgba(255,255,255,180); "
            "border-radius: 17px; color: #1D4B67; font-weight: 700; padding: 9px 15px; }"
        )
        self.action = QPushButton("Search", self)
        self.action.setStyleSheet(
            "QPushButton { background: #086F9D; color: white; border: 0; border-radius: 18px; "
            "font-weight: 700; padding: 10px 19px; }"
            "QPushButton:hover { background: #075C85; }"
        )
        self.note = QLabel(
            "Live backdrop sampling + Qt blur. No Apple proprietary refraction.", self
        )
        self.note.setStyleSheet("color: #315875; background: transparent; font-size: 12px;")
        self._build_scene()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._build_scene()
        self.title.setGeometry(52, 42, self.width() - 90, 50)
        self.subtitle.setGeometry(54, 91, self.width() - 90, 30)
        y = int(self.height() * 0.39)
        self.search.setGeometry(95, y + 20, max(180, self.width() - 390), 40)
        self.region.setGeometry(self.width() - 273, y + 19, 84, 42)
        self.action.setGeometry(self.width() - 178, y + 19, 126, 42)
        self.note.setGeometry(55, y + 116, self.width() - 95, 30)

    def _build_scene(self):
        w, h = max(1, self.width()), max(1, self.height())
        self._scene = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        p = QPainter(self._scene)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0, QColor("#E8F4FC"))
        bg.setColorAt(0.55, QColor("#C6E5F4"))
        bg.setColorAt(1, QColor("#DCD7FB"))
        p.fillRect(self._scene.rect(), bg)
        for x, y, radius, color in [
            (.18, .52, .23, QColor(22, 157, 202, 125)),
            (.77, .35, .29, QColor(123, 94, 221, 110)),
            (.56, .82, .22, QColor(45, 202, 178, 125)),
        ]:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(QPointF(w * x, h * y), w * radius, w * radius)
        p.setPen(QPen(QColor(255, 255, 255, 135), 2))
        for i in range(12):
            xx = (i + 1) * w / 13
            p.drawLine(int(xx), 0, int(xx - 130), h)
        p.end()
        self._blurred = blur_image(self._scene, 26)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.drawImage(0, 0, self._scene)
        y = int(self.height() * .39)
        rect = QRectF(52, y, self.width() - 104, 80)
        path = QPainterPath()
        path.addRoundedRect(rect, 34, 34)
        p.save()
        p.setClipPath(path)
        # Actual backdrop pixels, blurred before tint and edge highlights.
        p.drawImage(0, 0, self._blurred)
        tint = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        tint.setColorAt(0, QColor(255, 255, 255, 155))
        tint.setColorAt(1, QColor(222, 243, 255, 100))
        p.fillPath(path, tint)
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 230), 2.4))
        p.drawPath(path)
        inner = QPainterPath()
        inner.addRoundedRect(rect.adjusted(3, 3, -3, -3), 31, 31)
        p.setPen(QPen(QColor(77, 156, 206, 80), 1))
        p.drawPath(inner)
        p.setPen(QPen(QColor(255, 255, 255, 225), 2))
        p.drawArc(rect.adjusted(2, 2, -2, -2).toRect(), 27 * 16, 123 * 16)
        p.end()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("iCarcas — Glass Material Lab")
    window.setCentralWidget(GlassLab())
    window.resize(980, 600)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
