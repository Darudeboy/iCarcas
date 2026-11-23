"""iCarcas brand mark: static window icon + animated stacking layers splash."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def resources_dir() -> Path:
    return Path(__file__).resolve().parent / "resources"


def icon_png_path(*, transparent: bool = True) -> Path:
    """Prefer transparent mark so light theme does not show a black square."""
    names = (
        ("icarcas-icon-transparent.png", "icarcas-icon.png")
        if transparent
        else ("icarcas-icon.png", "icarcas-icon-transparent.png")
    )
    search_dirs = (
        resources_dir(),
        Path(__file__).resolve().parents[3] / "assets",
    )
    for directory in search_dirs:
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return resources_dir() / "icarcas-icon-transparent.png"


def load_app_icon() -> QIcon:
    path = icon_png_path()
    icon = QIcon()
    if path.is_file():
        pix = QPixmap(str(path))
        for size in (16, 24, 32, 48, 64, 128, 256):
            icon.addPixmap(
                pix.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
    else:
        for size in (16, 32, 64, 128):
            icon.addPixmap(_render_static_mark(size))
    return icon


def _render_static_mark(size: int, *, progress: float = 1.0) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    _paint_stack(painter, QRectF(0, 0, size, size), progress=progress)
    painter.end()
    return pix


def _layer_path(cx: float, cy: float, half_w: float, half_h: float) -> QPainterPath:
    """
    Rounded square rotated 45°, with independent half-width / half-height.

    Wider than tall (half_w > half_h) matches the brand PNG and avoids a
    side-squished diamond.
    """
    # Pre-rotation axis-aligned square that becomes a diamond of the desired span.
    # After 45° rotate: horizontal extent ≈ side * sqrt(2) * scale_x / 2 ...
    # Build a rounded rect, then rotate and non-uniformly scale around center.
    side = max(half_w, half_h) * math.sqrt(2)
    radius = side * 0.24
    rect = QRectF(cx - side / 2, cy - side / 2, side, side)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)

    # Uniform 45° diamond, then stretch to target half_w / half_h.
    # Uniform diamond half-extent = side / sqrt(2) = max(half_w, half_h).
    base = max(half_w, half_h)
    sx = half_w / base
    sy = half_h / base

    transform = QTransform()
    transform.translate(cx, cy)
    transform.scale(sx, sy)
    transform.rotate(45)
    transform.translate(-cx, -cy)
    return transform.map(path)


def _paint_stack(painter: QPainter, rect: QRectF, *, progress: float) -> None:
    """progress 0..1: layers fall from spread into compact stack."""
    progress = max(0.0, min(1.0, progress))
    t = 1.0 - (1.0 - progress) ** 3

    # Use full rect; prefer width so layers read wide like the PNG.
    w = rect.width()
    h = rect.height()
    cx = rect.center().x()
    # Slightly above center so glow + stack breathe inside the box.
    cy = rect.center().y() + h * 0.02

    # Layer face size — use most of the canvas width.
    half_w = w * 0.38
    half_h = h * 0.30  # a bit flatter than a pure square diamond

    # Soft aqua pool under the stack — matches brand PNG / Ink+Aqua UI.
    glow_alpha = int(70 * t)
    glow = QRadialGradient(QPointF(cx, cy + half_h * 0.9), max(w, h) * 0.48)
    glow.setColorAt(0.0, QColor(46, 196, 182, glow_alpha))
    glow.setColorAt(0.55, QColor(13, 148, 136, int(glow_alpha * 0.35)))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(glow)
    painter.drawEllipse(
        QPointF(cx, cy + half_h * 0.85),
        w * 0.42,
        h * 0.16,
    )

    # Compact final gaps; larger open spread while falling.
    base_gap = h * 0.085
    spread = h * 0.62
    thickness = h * 0.038

    for i in range(3):
        # Bottom (0) lands first, top (2) last.
        local = max(0.0, min(1.0, (t - i * 0.14) / 0.72))
        local_e = 1.0 - (1.0 - local) ** 2.4

        bounce = 1.0
        if 0.82 < local_e < 1.0:
            bounce = 1.0 + 0.055 * math.sin((local_e - 0.82) / 0.18 * math.pi)

        # Pop-in scale: slightly smaller while falling, settle to 1.0.
        scale = 0.88 + 0.12 * local_e

        # Rest positions: bottom below center, top above.
        rest_y = (1 - i) * base_gap * bounce
        fall_y = -(spread * (1.0 - local_e)) - (2 - i) * h * 0.06 * (1.0 - local_e)
        layer_cy = cy + rest_y + fall_y

        lw = half_w * scale
        lh = half_h * scale
        alpha = int(255 * (0.25 + 0.75 * local_e))

        # Thickness slab (isometric: slightly down) — deep teal edge.
        side = _layer_path(cx, layer_cy + thickness, lw, lh)
        painter.setBrush(QColor(8, 72, 68, int(alpha * 0.9)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(side)

        face = _layer_path(cx, layer_cy, lw, lh)
        grad = QLinearGradient(
            QPointF(cx - lw, layer_cy - lh),
            QPointF(cx + lw, layer_cy + lh),
        )
        if i == 2:
            # Top: mint / aqua (brand tip)
            grad.setColorAt(0.0, QColor(180, 255, 235, alpha))
            grad.setColorAt(0.4, QColor(94, 234, 212, alpha))
            grad.setColorAt(1.0, QColor(20, 160, 145, alpha))
        elif i == 1:
            grad.setColorAt(0.0, QColor(90, 220, 205, alpha))
            grad.setColorAt(1.0, QColor(15, 130, 120, alpha))
        else:
            grad.setColorAt(0.0, QColor(46, 196, 182, alpha))
            grad.setColorAt(1.0, QColor(12, 100, 95, alpha))

        painter.setBrush(grad)
        painter.setPen(
            QPen(QColor(200, 255, 240, int(65 * local_e)), max(1.2, w * 0.007))
        )
        painter.drawPath(face)


class StackingLogoWidget(QWidget):
    """Animated brand mark: three isometric layers landing into the icon."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        size: int = 160,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._progress = 0.0
        # Wider than tall so the diamond stack is not side-squished.
        self._w = width if width is not None else int(size * 1.2)
        self._h = height if height is not None else size
        self.setFixedSize(self._w, self._h)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(1650)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, value: float) -> None:
        self._progress = float(value)
        self.update()

    progress = Property(float, get_progress, set_progress)

    def play(self) -> None:
        self._anim.stop()
        self._progress = 0.0
        self._anim.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        # Small padding so strokes / glow are not clipped.
        pad = min(self._w, self._h) * 0.04
        _paint_stack(
            painter,
            QRectF(pad, pad, self._w - 2 * pad, self._h - 2 * pad),
            progress=self._progress,
        )
        painter.end()


class BrandSplash(QWidget):
    """Splash with stacking logo, then calls on_finished."""

    def __init__(
        self,
        *,
        mode: str = "dark",
        on_finished=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_finished = on_finished
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        from ios_restore.ui.theme import PALETTES

        p = PALETTES["dark" if mode == "dark" else "light"]
        bg, fg, muted, accent = p["bg"], p["text"], p["muted"], p["accent"]
        self.setStyleSheet(f"BrandSplash {{ background: {bg}; }}")
        self.setFixedSize(520, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 48, 36, 40)
        layout.setSpacing(16)
        layout.addStretch(1)

        self.logo = StackingLogoWidget(self, width=280, height=230)
        layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel()
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setText(
            f'<span style="font-family:\'Segoe UI Variable Display\',\'Bahnschrift SemiBold\','
            f'\'Segoe UI Semibold\',sans-serif; font-size:28px; font-weight:700;'
            f' letter-spacing:-0.3px;">'
            f'<span style="color:{accent}">i</span>'
            f'<span style="color:{fg}">Carcas</span></span>'
        )
        layout.addWidget(title)

        sub = QLabel("Загрузка…")
        sub.setObjectName("splashSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {muted}; font-size: 13px;")
        layout.addWidget(sub)
        layout.addStretch(1)

        self.logo._anim.finished.connect(self._finish)  # noqa: SLF001
        QTimer.singleShot(50, self.logo.play)

    def _finish(self) -> None:
        # Brief hold on the assembled mark before opening the main window.
        QTimer.singleShot(280, self._close_and_continue)

    def _close_and_continue(self) -> None:
        if self._on_finished:
            self._on_finished()
        self.close()
