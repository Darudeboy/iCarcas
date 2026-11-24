"""apple_ui — набор виджетов в стиле macOS / iOS для PySide6.

Тема:       set_theme("light" | "dark"); app.setStyleSheet(qss())
Кнопки:     AppleButton(text, kind="tinted" | "filled" | "danger" | "plain", large=False)
Навигация:  Sidebar (скользящая плашка выбора) + FadeStack (плавная смена страниц)
Контент:    Page, Group, Row, Tile, StatusDot, ProgressLine
"""
from __future__ import annotations

from string import Template

from PySide6.QtCore import (QEasingCurve, QEvent, QPoint, QPointF, QPropertyAnimation,
                            QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFrame,
                               QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)


def _no_top_flash(w: QWidget) -> None:
    """Orphan QWidgets briefly become native top-level HWNDs on Windows."""
    if w.parent() is None:
        w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)


def _clear_top_flash(w: QWidget) -> None:
    w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)


def _reveal_tree(root: QWidget) -> None:
    """Clear boot-time DontShowOnScreen on the window and every child."""
    _clear_top_flash(root)
    for child in root.findChildren(QWidget):
        _clear_top_flash(child)


class _ParentRevealMixin:
    """Drop DontShowOnScreen as soon as the widget gets a real parent."""

    def event(self, e):  # noqa: N802
        if e.type() == QEvent.Type.ParentChange and self.parent() is not None:  # type: ignore[attr-defined]
            _clear_top_flash(self)  # type: ignore[arg-type]
        return super().event(e)  # type: ignore[misc]

# --------------------------------------------------------------------------- тема
PALETTES = {
    "light": dict(bg="#F2F2F7", side="#E9E9EE", group="#FFFFFF", sep="#E5E5EA",
                  text="#1C1C1E", sub="#8E8E93", blue="#007AFF", blue_soft="#E5F1FF",
                  green="#34C759", red="#FF3B30", orange="#FF9500", purple="#AF52DE",
                  gray="#8E8E93", log="#FAFAFC"),
    "dark": dict(bg="#1C1C1E", side="#151517", group="#2C2C2E", sep="#3A3A3C",
                 text="#F5F5F7", sub="#98989F", blue="#0A84FF", blue_soft="#0A2A4A",
                 green="#30D158", red="#FF453A", orange="#FF9F0A", purple="#BF5AF2",
                 gray="#8E8E93", log="#141416"),
}
P: dict[str, QColor] = {}
_hex: dict[str, str] = {}


def set_theme(mode: str) -> None:
    _hex.clear(); _hex.update(PALETTES[mode])
    P.clear(); P.update({k: QColor(v) for k, v in _hex.items()})


def mix(c: QColor, alpha: float) -> QColor:
    c = QColor(c); c.setAlphaF(max(0.0, min(1.0, alpha))); return c


_QSS = Template("""
* { color: $text; font-size: 13px; }
QMainWindow, QWidget#root, QWidget#content { background: $bg; }
QWidget#sidebar { background: $side; border-right: 1px solid $sep; }
QFrame#group { background: $group; border-radius: 12px; }
QLabel { background: transparent; }
QLabel#large { font-size: 28px; font-weight: 700; }
QLabel#brand { font-size: 22px; font-weight: 700; }
QLabel#sub, QLabel#footnote, QLabel#rowSub, QLabel#privacyNotice { color: $sub; }
QLabel#footnote, QLabel#rowSub, QLabel#privacyNotice { font-size: 12px; }
QLabel#rowTitle { font-size: 14px; font-weight: 500; }
QLabel#downloadStateTitle { font-size: 14px; font-weight: 600; }
QLabel#downloadStateDetail, QLabel#downloadProgressLabel { color: $sub; font-size: 12px; }
QFrame#downloadStatusPanel { background: $group; border-radius: 12px; }
QLineEdit { background: $group; border: 1px solid $sep; border-radius: 12px;
            padding: 12px 14px; font-size: 14px;
            selection-background-color: $blue; selection-color: white; }
QCheckBox { spacing: 8px; color: $text; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px;
    border: 1px solid $sep; background: $group; }
QCheckBox::indicator:checked { background: $blue; border-color: $blue; }
QProgressBar { background: $sep; border: none; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: $blue; border-radius: 4px; }
QPlainTextEdit#log { background: $log; border: none; border-radius: 12px; padding: 14px;
    font-family: "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace; font-size: 12px; color: $sub; }
QPushButton#regionTag {
    background: $group; color: $text; border: 1px solid $sep; border-radius: 10px;
    padding: 8px 10px; font-size: 12px; font-weight: 500;
}
QPushButton#regionTag[state="ok"] {
    background: $blue_soft; color: $blue; border-color: $blue;
    font-weight: 600;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $sep; border-radius: 3px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: $group; color: $text; border: 1px solid $sep; padding: 6px 8px; }
""")


def qss() -> str:
    return _QSS.substitute(_hex)


set_theme("light")


def styled(w: QWidget, name: str) -> QWidget:
    w.setObjectName(name); w.setAttribute(Qt.WA_StyledBackground, True); return w


# ------------------------------------------------------------------ иконки-глифы
def draw_glyph(p: QPainter, kind: str, r: QRectF) -> None:
    p.save()
    white = QColor("white"); c = r.center()
    p.setPen(QPen(white, 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.setBrush(Qt.NoBrush)
    if kind == "phone":
        p.drawRoundedRect(QRectF(c.x() - 4.5, c.y() - 8, 9, 16), 2.4, 2.4)
        p.drawLine(QPointF(c.x() - 1.5, c.y() + 5), QPointF(c.x() + 1.5, c.y() + 5))
    elif kind == "person":
        p.drawEllipse(QPointF(c.x(), c.y() - 3.5), 3.2, 3.2)
        path = QPainterPath(QPointF(c.x() - 6, c.y() + 8))
        path.cubicTo(c.x() - 6, c.y() + 2, c.x() + 6, c.y() + 2, c.x() + 6, c.y() + 8)
        p.drawPath(path)
    elif kind == "app":
        p.setPen(Qt.NoPen); p.setBrush(white)
        for ox, oy in ((-6.5, -6.5), (1, -6.5), (-6.5, 1), (1, 1)):
            p.drawRoundedRect(QRectF(c.x() + ox, c.y() + oy, 5.5, 5.5), 1.4, 1.4)
    elif kind == "log":
        for i, o in enumerate((-5, 0, 5)):
            p.drawLine(QPointF(c.x() - 6, c.y() + o), QPointF(c.x() + 6 - (4 if i == 2 else 0), c.y() + o))
    elif kind == "start":
        p.setPen(Qt.NoPen); p.setBrush(white)
        p.drawPolygon(QPolygonF([QPointF(c.x() - 3, c.y() - 6), QPointF(c.x() - 3, c.y() + 6),
                                 QPointF(c.x() + 6, c.y())]))
    p.restore()


class Tile(_ParentRevealMixin, QWidget):
    """Цветной скруглённый квадрат: буква шага, а после выполнения — галочка."""
    def __init__(self, color="blue", letter="", size=30, parent=None):
        super().__init__(parent)
        _no_top_flash(self)
        self.color, self.letter, self.done = color, letter, False
        self.setFixedSize(size, size)

    def set_done(self, done: bool) -> None:
        self.done = done; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()); p.setPen(Qt.NoPen)
        p.setBrush(P["green"] if self.done else P[self.color])
        p.drawRoundedRect(r, r.width() * .27, r.width() * .27)
        c = r.center()
        if self.done:
            p.setPen(QPen(QColor("white"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            path = QPainterPath(QPointF(c.x() - 5, c.y() + .5))
            path.lineTo(c.x() - 1.5, c.y() + 4); path.lineTo(c.x() + 5, c.y() - 3.5); p.drawPath(path)
        else:
            f = QFont(self.font()); f.setPixelSize(14); f.setWeight(QFont.Bold); p.setFont(f)
            p.setPen(QColor("white")); p.drawText(r, Qt.AlignCenter, self.letter)


# --------------------------------------------------------------------- кнопки
class HoverButton(_ParentRevealMixin, QAbstractButton):
    """База: плавное наведение (_h) и нажатие (_p), 0..1."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        _no_top_flash(self)
        if text:
            self.setText(text)
        self._h = self._p = 0.0
        self._ha, self._pa = QVariantAnimation(self), QVariantAnimation(self)
        self._ha.setDuration(160); self._pa.setDuration(110)
        self._ha.valueChanged.connect(lambda v: self._set("_h", v))
        self._pa.valueChanged.connect(lambda v: self._set("_p", v))
        self.setCursor(Qt.PointingHandCursor); self.setFocusPolicy(Qt.StrongFocus)

    def _set(self, name, v): setattr(self, name, float(v)); self.update()

    def _go(self, a, cur, to):
        a.stop(); a.setStartValue(float(cur)); a.setEndValue(float(to)); a.start()

    def enterEvent(self, e): self._go(self._ha, self._h, 1); super().enterEvent(e)
    def leaveEvent(self, e): self._go(self._ha, self._h, 0); super().leaveEvent(e)
    def mousePressEvent(self, e): self._go(self._pa, self._p, 1); super().mousePressEvent(e)
    def mouseReleaseEvent(self, e): self._go(self._pa, self._p, 0); super().mouseReleaseEvent(e)


class AppleButton(HoverButton):
    def __init__(self, text, kind="tinted", large=False, parent=None):
        super().__init__(text, parent)
        self.kind, self.large, self._kbd = kind, large, False
        self.setFixedHeight(48 if large else 34)
        self.setSizePolicy(QSizePolicy.Expanding if large else QSizePolicy.Minimum, QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + (48 if self.large else 32),
                     48 if self.large else 34)

    def focusInEvent(self, e):
        self._kbd = e.reason() in (Qt.TabFocusReason, Qt.BacktabFocusReason); super().focusInEvent(e)
    def focusOutEvent(self, e): self._kbd = False; super().focusOutEvent(e)

    def _colors(self):
        h, k = self._h, self.kind
        if k == "filled": return QColor(P["blue"]).lighter(100 + int(10 * h)), QColor("white")
        if k == "danger": return mix(P["red"], .12 + .10 * h), P["red"]
        if k == "plain":  return mix(P["sub"], .16 * h), P["blue"]
        return mix(P["blue"], .13 + .10 * h), P["blue"]

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled(): p.setOpacity(.4)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2); c = r.center(); s = 1 - .03 * self._p
        p.translate(c); p.scale(s, s); p.translate(-c)
        bg, fg = self._colors(); rad = 12 if self.large else 9
        p.setPen(Qt.NoPen); p.setBrush(bg); p.drawRoundedRect(r, rad, rad)
        if self._kbd:
            p.setBrush(Qt.NoBrush); p.setPen(QPen(mix(P["blue"], .55), 2))
            p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), rad + 1, rad + 1)
        f = QFont(self.font()); f.setPixelSize(15 if self.large else 13)
        f.setWeight(QFont.DemiBold if self.kind == "filled" else QFont.Medium); p.setFont(f)
        p.setPen(fg); p.drawText(r, Qt.AlignCenter, self.text())


# -------------------------------------------------------------------- навигация
class NavItem(HoverButton):
    def __init__(self, text, glyph, color, parent=None):
        super().__init__(text, parent)
        self.glyph, self.color = glyph, color
        self.setCheckable(True); self.setFixedHeight(40)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); h = self.height()
        if not self.isChecked() and self._h:
            p.setPen(Qt.NoPen); p.setBrush(mix(P["sub"], .13 * self._h))
            p.drawRoundedRect(QRectF(self.rect()), 9, 9)
        tile = QRectF(10, (h - 26) / 2, 26, 26)
        p.setPen(Qt.NoPen); p.setBrush(P[self.color]); p.drawRoundedRect(tile, 7, 7)
        draw_glyph(p, self.glyph, tile)
        f = QFont(self.font()); f.setPixelSize(14)
        f.setWeight(QFont.DemiBold if self.isChecked() else QFont.Medium); p.setFont(f)
        p.setPen(P["text"])
        p.drawText(QRectF(46, 0, self.width() - 52, h), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class _Pill(QWidget):
    def __init__(self, parent):
        super().__init__(parent); self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen); p.setBrush(mix(P["blue"], .16))
        p.drawRoundedRect(QRectF(self.rect()), 9, 9)


class Sidebar(_ParentRevealMixin, QWidget):
    selected = Signal(int)

    def __init__(self, entries, version="", parent=None):
        super().__init__(parent)
        _no_top_flash(self)
        styled(self, "sidebar"); self.setFixedWidth(232); self._i = 0
        outer = QVBoxLayout(self); outer.setContentsMargins(14, 24, 14, 16); outer.setSpacing(20)
        self.brand = QLabel(self); self.brand.setObjectName("brand"); self.brand.setTextFormat(Qt.RichText)
        self.brand.setContentsMargins(10, 0, 0, 0); outer.addWidget(self.brand)

        self.holder = QWidget(self); hl = QVBoxLayout(self.holder)
        hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(2)
        self.pill = _Pill(self.holder)                      # создан первым → лежит под кнопками
        self.group = QButtonGroup(self); self.items: list[NavItem] = []
        for k, (text, glyph, color) in enumerate(entries):
            it = NavItem(text, glyph, color, parent=self.holder)
            self.group.addButton(it); hl.addWidget(it)
            it.clicked.connect(lambda _=False, k=k: self.select(k)); self.items.append(it)
        hl.addStretch(1); outer.addWidget(self.holder, 1)

        ver = QLabel(version, self); ver.setObjectName("sub"); ver.setContentsMargins(10, 0, 0, 0)
        outer.addWidget(ver)
        self._anim = QPropertyAnimation(self.pill, b"geometry", self)
        self._anim.setDuration(300); self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.retheme()

    def retheme(self):
        self.brand.setText(f'<span style="color:{_hex["blue"]}">i</span>Carcas')

    def select(self, i, animate=True, emit=True):
        self._i = i; self.items[i].setChecked(True); g = self.items[i].geometry()
        if animate and self.isVisible() and g.isValid():
            self._anim.stop(); self._anim.setStartValue(self.pill.geometry())
            self._anim.setEndValue(g); self._anim.start()
        else:
            self.pill.setGeometry(g)
        if emit: self.selected.emit(i)

    def _snap(self):
        if self._anim.state() == QPropertyAnimation.Stopped:
            self.pill.setGeometry(self.items[self._i].geometry())

    def showEvent(self, e): super().showEvent(e); QTimer.singleShot(0, self._snap)
    def resizeEvent(self, e): super().resizeEvent(e); QTimer.singleShot(0, self._snap)


class FadeStack(QStackedWidget):
    """Страницы появляются с затуханием и лёгким сдвигом снизу."""
    def go(self, i: int) -> None:
        if i == self.currentIndex(): return
        w = self.widget(i); self.setCurrentIndex(i)
        eff = QGraphicsOpacityEffect(w); w.setGraphicsEffect(eff)
        fade = QPropertyAnimation(eff, b"opacity", w); fade.setDuration(260)
        fade.setStartValue(0.0); fade.setEndValue(1.0); fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.finished.connect(lambda: w.setGraphicsEffect(None))
        end = w.pos(); slide = QPropertyAnimation(w, b"pos", w); slide.setDuration(320)
        slide.setStartValue(end + QPoint(0, 12)); slide.setEndValue(end)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        # Keep refs so GC does not kill animations mid-flight (looks like a freeze).
        w._icarcas_fade = fade  # type: ignore[attr-defined]
        w._icarcas_slide = slide  # type: ignore[attr-defined]
        fade.start()
        slide.start()


# -------------------------------------------------------------------- контент
class StatusDot(_ParentRevealMixin, QWidget):
    """Серая точка → зелёная с мягкой пульсацией, когда состояние «on»."""
    def __init__(self, parent=None):
        super().__init__(parent)
        _no_top_flash(self)
        self.setFixedSize(16, 16); self.state, self._t = "off", 0.0
        self._a = QVariantAnimation(self); self._a.setDuration(1900); self._a.setLoopCount(-1)
        self._a.setStartValue(0.0); self._a.setEndValue(1.0)
        self._a.valueChanged.connect(lambda v: (setattr(self, "_t", float(v)), self.update()))

    def set_state(self, state: str) -> None:       # "off" | "on" | "busy"
        self.state = state
        (self._a.start if state == "on" else self._a.stop)(); self._t = 0.0; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setPen(Qt.NoPen)
        col = {"on": P["green"], "busy": P["orange"]}.get(self.state, P["gray"]); c = QPointF(8, 8)
        if self.state == "on":
            p.setBrush(mix(col, .45 * (1 - self._t))); p.drawEllipse(c, 4 + 4 * self._t, 4 + 4 * self._t)
        p.setBrush(col); p.drawEllipse(c, 4.5, 4.5)


class ProgressLine(_ParentRevealMixin, QWidget):
    """Тонкая бегущая полоска под верхним краем — «идёт операция»."""
    def __init__(self, parent=None):
        super().__init__(parent)
        _no_top_flash(self)
        self.setFixedHeight(3); self.hide(); self._t = 0.0
        self._a = QVariantAnimation(self); self._a.setDuration(1300); self._a.setLoopCount(-1)
        self._a.setStartValue(0.0); self._a.setEndValue(1.0); self._a.setEasingCurve(QEasingCurve.InOutSine)
        self._a.valueChanged.connect(lambda v: (setattr(self, "_t", float(v)), self.update()))

    def set_busy(self, busy: bool) -> None:
        if busy: self.show(); self._a.start()
        else: self._a.stop(); self.hide()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setPen(Qt.NoPen)
        w = self.width(); seg = w * .32; x = -seg + (w + seg) * self._t
        p.setBrush(P["blue"]); p.drawRoundedRect(QRectF(x, 0, seg, 3), 1.5, 1.5)


class _Sep(_ParentRevealMixin, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _no_top_flash(self)
        self.setFixedHeight(1)

    def paintEvent(self, _):
        QPainter(self).fillRect(16, 0, self.width() - 16, 1, P["sep"])


class Group(_ParentRevealMixin, QFrame):
    """Сгруппированный список как в «Настройках» iOS."""
    def __init__(self, parent=None):
        super().__init__(parent)
        _no_top_flash(self)
        self.setObjectName("group")
        self._l = QVBoxLayout(self); self._l.setContentsMargins(0, 0, 0, 0); self._l.setSpacing(0)

    def add(self, w: QWidget) -> QWidget:
        if self._l.count():
            self._l.addWidget(_Sep(self))
        self._l.addWidget(w)
        _clear_top_flash(w)
        return w


class Row(_ParentRevealMixin, QWidget):
    def __init__(self, title, sub="", lead: QWidget | None = None, dot=False, parent=None):
        super().__init__(parent)
        _no_top_flash(self)
        h = QHBoxLayout(self); h.setContentsMargins(16, 12, 14, 12); h.setSpacing(12)
        if lead:
            h.addWidget(lead)
            _clear_top_flash(lead)
        self.dot = StatusDot(self) if dot else None
        if self.dot:
            h.addWidget(self.dot)
        col = QVBoxLayout(); col.setSpacing(1)
        self.title = QLabel(title, self); self.title.setObjectName("rowTitle")
        self.sub = QLabel(sub, self); self.sub.setObjectName("rowSub"); self.sub.setVisible(bool(sub))
        col.addWidget(self.title); col.addWidget(self.sub); h.addLayout(col, 1)
        self.tail = QHBoxLayout(); self.tail.setSpacing(8); h.addLayout(self.tail)

    def set_sub(self, text: str) -> None:
        self.sub.setText(text); self.sub.setVisible(bool(text))

    def add_tail(self, w: QWidget) -> QWidget:
        self.tail.addWidget(w, 0, Qt.AlignVCenter)
        _clear_top_flash(w)
        return w


class Page(_ParentRevealMixin, QWidget):
    def __init__(self, title, subtitle="", parent=None):
        super().__init__(parent)
        _no_top_flash(self)
        self.lay = QVBoxLayout(self); self.lay.setContentsMargins(36, 30, 36, 28); self.lay.setSpacing(16)
        head = QHBoxLayout(); col = QVBoxLayout(); col.setSpacing(2)
        t = QLabel(title, self); t.setObjectName("large")
        s = QLabel(subtitle, self); s.setObjectName("sub")
        col.addWidget(t); col.addWidget(s); head.addLayout(col, 1)
        self.head_tail = QHBoxLayout(); head.addLayout(self.head_tail); self.lay.addLayout(head)
