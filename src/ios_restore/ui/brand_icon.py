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
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QLabel,
    QSplashScreen,
    QVBoxLayout,
    QWidget,
)


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


def render_boot_pixmap(
    mode: str,
    *,
    progress: float = 1.0,
    brand_opacity: float = 1.0,
    subtitle: str = "Загрузка…",
    width: int = 520,
    height: int = 480,
) -> QPixmap:
    """Off-screen frame for QSplashScreen — no live QWidget chrome to flicker."""
    from ios_restore.ui.theme import PALETTES

    p = PALETTES["dark" if mode == "dark" else "light"]
    bg = QColor(p["bg"])
    fg = QColor(p["text"])
    muted = QColor(p["muted"])
    accent = QColor(p["accent"])

    pix = QPixmap(width, height)
    pix.fill(bg)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    alpha = max(0.0, min(1.0, brand_opacity))
    if alpha > 0.01:
        painter.setOpacity(alpha)
        logo_w, logo_h = 280, 230
        logo_x = (width - logo_w) / 2
        logo_y = height * 0.18
        pad = min(logo_w, logo_h) * 0.04
        _paint_stack(
            painter,
            QRectF(logo_x + pad, logo_y + pad, logo_w - 2 * pad, logo_h - 2 * pad),
            progress=progress,
        )

        from PySide6.QtGui import QFont

        title_font = QFont("Segoe UI Semibold")
        title_font.setPixelSize(28)
        title_font.setWeight(QFont.Weight.Bold)
        painter.setFont(title_font)
        title_y = int(logo_y + logo_h + 18)
        # Draw "i" in accent, "Carcas" in fg.
        metrics = painter.fontMetrics()
        full = "iCarcas"
        full_w = metrics.horizontalAdvance(full)
        tx = (width - full_w) / 2
        painter.setPen(accent)
        painter.drawText(int(tx), title_y + metrics.ascent(), "i")
        painter.setPen(fg)
        painter.drawText(
            int(tx + metrics.horizontalAdvance("i")),
            title_y + metrics.ascent(),
            "Carcas",
        )

        sub_font = QFont("Segoe UI")
        sub_font.setPixelSize(13)
        painter.setFont(sub_font)
        painter.setPen(muted)
        sub_rect = QRectF(0, title_y + metrics.height() + 10, width, 24)
        painter.drawText(sub_rect, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), subtitle)

    painter.end()
    return pix


class BrandSplash(QSplashScreen):
    """Pixmap splash: pre-render a smooth reel once, then play by index.

    Full paints on every animation tick froze the IDE; cached frames flip cheaply
    while still looking fluid (~30 fps).
    """

    _FADE_FRAMES = 12
    _LAYER_FRAMES = 36

    def __init__(
        self,
        *,
        mode: str = "dark",
        on_finished=None,
        parent: QWidget | None = None,
    ) -> None:
        self._mode = "dark" if mode == "dark" else "light"
        self._on_finished = on_finished
        self._closed = False
        self._handoff_window: QWidget | None = None
        self._frames: list[QPixmap] = []
        self._anim: QVariantAnimation | None = None
        self._cover = render_boot_pixmap(
            self._mode, progress=1.0, brand_opacity=0.0, subtitle=""
        )
        super().__init__(self._cover, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

    def show_cover(self) -> None:
        """Show solid theme plate immediately (pre-rendered, no empty widget)."""
        self.setPixmap(self._cover)
        self.show()
        self.raise_()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    @staticmethod
    def _ease_out_cubic(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return 1.0 - (1.0 - t) ** 3

    def _build_reel(self) -> list[QPixmap]:
        frames: list[QPixmap] = []
        # 1) Soft fade-in of the assembled mark.
        for i in range(self._FADE_FRAMES):
            t = (i + 1) / self._FADE_FRAMES
            frames.append(
                render_boot_pixmap(
                    self._mode,
                    progress=1.0,
                    brand_opacity=self._ease_out_cubic(t),
                    subtitle="Загрузка…",
                )
            )
        # 2) Layer drop — denser sampling + easing for a smooth fall.
        for i in range(self._LAYER_FRAMES):
            t = i / max(1, self._LAYER_FRAMES - 1)
            frames.append(
                render_boot_pixmap(
                    self._mode,
                    progress=self._ease_out_cubic(t),
                    brand_opacity=1.0,
                    subtitle="Собираем…",
                )
            )
        frames.append(
            render_boot_pixmap(
                self._mode, progress=1.0, brand_opacity=1.0, subtitle="Готово"
            )
        )
        return frames

    def start_brand(self, handoff_window: QWidget | None = None) -> None:
        self._handoff_window = handoff_window
        self.show_cover()
        self._frames = self._build_reel()
        if not self._frames:
            self._handoff()
            return

        anim = QVariantAnimation(self)
        # ~33 ms/frame ≈ 30 fps; duration matches reel length.
        anim.setDuration(max(400, len(self._frames) * 33))
        anim.setStartValue(0.0)
        anim.setEndValue(float(len(self._frames) - 1))
        anim.setEasingCurve(QEasingCurve.Type.Linear)

        def _tick(v: object) -> None:
            if self._closed or not self._frames:
                return
            idx = int(round(float(v)))
            idx = max(0, min(len(self._frames) - 1, idx))
            self.setPixmap(self._frames[idx])

        anim.valueChanged.connect(_tick)
        anim.finished.connect(self._after_reel)
        self._anim = anim
        # Show first frame immediately, then run.
        self.setPixmap(self._frames[0])
        anim.start()
        QTimer.singleShot(anim.duration() + 800, self._handoff)

    def _after_reel(self) -> None:
        if self._frames:
            self.setPixmap(self._frames[-1])
        QTimer.singleShot(280, self._handoff)

    def _handoff(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._anim is not None:
            self._anim.stop()
        window = self._handoff_window
        callback = self._on_finished
        # Free frame memory before showing the main UI.
        self._frames.clear()
        if window is not None:
            from ios_restore.ui import apple_ui as aui

            aui._reveal_tree(window)  # noqa: SLF001
            window.show()
            window.raise_()
            window.activateWindow()
            try:
                self.finish(window)
            except Exception:  # noqa: BLE001
                self.close()
            if callback:
                callback()
            return
        self.close()
        if callback:
            callback()
