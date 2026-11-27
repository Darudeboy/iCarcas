"""Custom-painted glass search for iCarcas; independent of download logic."""
from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy


class _FocusWatcher(QObject):
    def __init__(self, surface):
        super().__init__(surface)
        self.surface = surface

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn:
            self.surface.animate_focus(True)
        elif event.type() == QEvent.Type.FocusOut:
            self.surface.animate_focus(False)
        return False


class _GlassRegion(QComboBox):
    """Custom closed-state appearance, while preserving QComboBox data API."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setFixedWidth(96)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Регион App Store")
        self.setStyleSheet("""
            QComboBox { background: transparent; border: 0; color: transparent; }
            QComboBox::drop-down { border: 0; width: 0; }
            QComboBox QAbstractItemView {
                background: #F7FAFF; color: #193B53;
                border: 1px solid #C9DDEB;
                selection-background-color: #D7ECF7;
                selection-color: #0B526F; padding: 5px;
            }
        """)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor(255, 255, 255, 190), 1))
        painter.setBrush(QColor(255, 255, 255, 115))
        painter.drawRoundedRect(rect, 17, 17)
        code = str(self.currentData() or self.currentText())
        if "·" in code:
            code = code.rsplit("·", 1)[-1].strip()
        painter.setPen(QColor("#173F5B"))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect.adjusted(13, 0, -23, 0), Qt.AlignmentFlag.AlignVCenter, code[:5])
        arrow = QPainterPath()
        x, y = rect.right() - 15, rect.center().y()
        arrow.moveTo(x - 4, y - 2)
        arrow.lineTo(x, y + 2)
        arrow.lineTo(x + 4, y - 2)
        painter.setPen(QPen(QColor("#47738B"), 1.7))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(arrow)


class LiquidSearchBar(QFrame):
    """Animated translucent search material; no OS backdrop blur."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("liquidSearch")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._focus_amount = 0.0
        self._focus_animation = QPropertyAnimation(self, b"focusAmount", self)
        self._focus_animation.setDuration(240)
        self._focus_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(23, 13, 13, 13)
        layout.setSpacing(12)
        icon = QLabel("⌕", self)
        icon.setStyleSheet("background: transparent; color: #497B9B; font-size: 27px;")
        icon.setFixedWidth(25)
        layout.addWidget(icon)
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Найти приложение, Store ID или Bundle ID")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(0)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: none; background: transparent; color: #183B55;
                selection-background-color: #A7D8EE;
                font-size: 15px; padding: 5px 0;
            }
        """)
        layout.addWidget(self.search_input, 1)
        self.region_selector = _GlassRegion(self)
        self.region_selector.currentIndexChanged.connect(lambda _: self.region_selector.update())
        layout.addWidget(self.region_selector)
        self.search_button = QPushButton("Найти", self)
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.setFixedHeight(42)
        self.search_button.setMinimumWidth(96)
        self.search_button.setStyleSheet("""
            QPushButton {
                color: white; font-weight: 700; font-size: 13px;
                border: 1px solid rgba(255,255,255,85);
                border-radius: 19px;
                background-color: #087EAD; padding: 8px 18px;
            }
            QPushButton:hover { background-color: #076B98; }
            QPushButton:pressed { background-color: #075A80; }
            QPushButton:disabled { background-color: #91B6C7; }
        """)
        layout.addWidget(self.search_button)
        self._focus_watcher = _FocusWatcher(self)
        self.search_input.installEventFilter(self._focus_watcher)

    def get_focus_amount(self):
        return self._focus_amount

    def set_focus_amount(self, amount):
        self._focus_amount = amount
        self.update()

    focusAmount = Property(float, get_focus_amount, set_focus_amount)

    def animate_focus(self, focused):
        self._focus_animation.stop()
        self._focus_animation.setStartValue(self._focus_amount)
        self._focus_animation.setEndValue(1.0 if focused else 0.0)
        self._focus_animation.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect().adjusted(2, 2, -2, -2)
        shape = QPainterPath()
        shape.addRoundedRect(outer, 29, 29)
        body = QLinearGradient(0, outer.top(), 0, outer.bottom())
        body.setColorAt(0, QColor(255, 255, 255, 222))
        body.setColorAt(0.52, QColor(233, 245, 255, 175))
        body.setColorAt(1, QColor(205, 230, 246, 145))
        p.fillPath(shape, body)
        rim = QColor(97, 173, 218, int(75 + 135 * self._focus_amount))
        p.setPen(QPen(rim, 1.5 + self._focus_amount))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(shape)
        p.setPen(QPen(QColor(255, 255, 255, 225), 1.7))
        p.drawArc(outer.adjusted(2, 2, -2, -2), 25 * 16, 130 * 16)
        p.setPen(QPen(QColor(76, 134, 172, 65), 1))
        p.drawArc(outer.adjusted(2, 2, -2, -2), 205 * 16, 130 * 16)
