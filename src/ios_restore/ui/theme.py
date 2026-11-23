"""Тема iCarcas: токены + QSS. Подключается одной строкой:

    app.setStyleSheet(build_stylesheet("dark"))   # или "light"

Визуальный язык: Ink + Aqua (как у логотипа — слои teal/mint),
не generic blue и не «AI purple».

Кнопки и метки:
    QPushButton            -> обычная кнопка
    setProperty("variant", "primary" | "danger" | "ghost" | "header")
    QFrame#card            -> секция
    QLabel#stepBadge       -> кружок шага, property state = idle | active | done
    QLabel#chip            -> плашка статуса, property state = idle | ok
    QToolButton#cornerChip -> угол: iOS / сессия
    QPushButton[variant=header] -> компактные кнопки в шапке
    QLabel#privacyNotice   -> локальное хранение УЗ
    QPlainTextEdit#log     -> журнал
"""
from __future__ import annotations

from string import Template

from PySide6.QtGui import QColor, QPalette

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#0A0F14",
        "surface": "#121A22",
        "surface2": "#1A2430",
        "hover": "#243040",
        "pressed": "#2C3A4C",
        "border": "#1E2A36",
        "border_strong": "#334556",
        "text": "#E8EEF2",
        "muted": "#8FA3B3",
        "accent": "#2EC4B6",
        "accent_hover": "#45D4C6",
        "accent_text": "#04201C",
        "accent_dim": "#163A38",
        "accent_dim_text": "#9FE8DF",
        "danger": "#F07178",
        "danger_bg": "#2A161A",
        "danger_border": "#5C2E34",
        "ok": "#3DDC97",
        "ok_bg": "#12281F",
        "ok_border": "#1F5A40",
        "log_bg": "#070B10",
    },
    "light": {
        "bg": "#E8EEF2",
        "surface": "#F7FAFC",
        "surface2": "#EEF3F7",
        "hover": "#E0E8EE",
        "pressed": "#D3DDE6",
        "border": "#D2DCE5",
        "border_strong": "#A8B8C6",
        "text": "#0F1A22",
        "muted": "#5A6F7F",
        "accent": "#0D9488",
        "accent_hover": "#0FABA0",
        "accent_text": "#FFFFFF",
        "accent_dim": "#C5EDE8",
        "accent_dim_text": "#0F5C55",
        "danger": "#D64550",
        "danger_bg": "#FDEEEE",
        "danger_border": "#F0B8BC",
        "ok": "#0F9F6E",
        "ok_bg": "#E3F7EE",
        "ok_border": "#9AD4BB",
        "log_bg": "#F0F4F7",
    },
}

_QSS = Template(
    """
* {
    font-family: "Segoe UI Variable Text", "Segoe UI", "Bahnschrift", sans-serif;
    font-size: 14px;
    color: $text;
}
QWidget#root { background: $bg; }
QScrollArea#mainScroll { background: $bg; border: none; }
QScrollArea#mainScroll > QWidget > QWidget { background: $bg; }

/* ---------- Заголовок ---------- */
QLabel#appTitle {
    font-family: "Segoe UI Variable Display", "Bahnschrift SemiBold", "Segoe UI Semibold", sans-serif;
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -0.4px;
}
QLabel#appSubtitle {
    color: $muted;
    font-size: 13px;
    line-height: 1.4;
    letter-spacing: 0.1px;
}
QLabel#hint {
    color: $muted;
    font-size: 13px;
    line-height: 1.45;
}

/* ---------- Секции ---------- */
QFrame#card {
    background: $surface;
    border: 1px solid $border;
    border-radius: 18px;
}
QLabel#cardTitle {
    font-family: "Segoe UI Variable Display", "Bahnschrift SemiBold", "Segoe UI Semibold", sans-serif;
    font-size: 15px;
    font-weight: 650;
    letter-spacing: 0.2px;
}
QLabel#cardStatus { color: $muted; font-size: 12px; }

/* ---------- Шаги ---------- */
QLabel#stepBadge {
    min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
    border-radius: 9px;
    background: $surface2; color: $muted;
    border: 1px solid $border_strong;
    font-weight: 700; font-size: 12px;
}
QLabel#stepBadge[state="active"] {
    background: $accent; color: $accent_text; border-color: $accent;
}
QLabel#stepBadge[state="done"] {
    background: $ok_bg; color: $ok; border-color: $ok_border;
}

/* ---------- Плашки статуса ---------- */
QLabel#chip {
    background: $surface2; color: $muted;
    border: 1px solid $border; border-radius: 8px;
    padding: 4px 10px; font-size: 12px;
}
QLabel#chip[state="ok"] { background: $ok_bg; color: $ok; border-color: $ok_border; }

QToolButton#cornerChip {
    background: $surface2; color: $text;
    border: 1px solid $border; border-radius: 10px;
    padding: 8px 14px; font-size: 13px; font-weight: 600;
    min-width: 92px;
}
QToolButton#cornerChip[state="ok"],
QToolButton#cornerChip[state="busy"] {
    background: $ok_bg; color: $ok; border-color: $ok_border;
}
QToolButton#cornerChip:hover { background: $hover; border-color: $accent; }
QToolButton#cornerChip[state="ok"]:hover,
QToolButton#cornerChip[state="busy"]:hover {
    background: $ok_bg; border-color: $ok; color: $ok;
}
QToolButton#cornerChip:disabled { color: $muted; background: transparent; }
QToolButton#cornerChip[state="ok"]:disabled,
QToolButton#cornerChip[state="busy"]:disabled {
    background: $ok_bg; color: $ok; border-color: $ok_border;
}

QLabel#privacyNotice {
    color: $muted;
    font-size: 12px;
    line-height: 1.45;
    padding: 0 2px 4px 2px;
}
QLabel#helpBody {
    color: $text;
    font-size: 14px;
    line-height: 1.5;
}

QPushButton#regionTag {
    background: $surface2; color: $muted;
    border: 1px solid $border; border-radius: 8px;
    padding: 7px 10px; font-size: 12px; font-weight: 600;
}
QPushButton#regionTag[state="ok"] {
    background: $accent_dim; color: $accent_dim_text; border-color: $accent;
}
QPushButton#regionTag:hover {
    background: $hover; border-color: $border_strong; color: $text;
}
QPushButton#regionTag[state="ok"]:hover {
    background: $accent_dim; color: $accent_dim_text; border-color: $accent;
}
QPushButton#regionTag:disabled {
    color: $muted; background: transparent;
}
QPushButton#regionTag[state="ok"]:disabled {
    background: $accent_dim; color: $accent_dim_text; border-color: $accent;
}

/* ---------- Кнопки ---------- */
QPushButton {
    background: $surface2;
    border: 1px solid $border;
    border-radius: 11px;
    padding: 10px 16px;
    font-weight: 550;
}
QPushButton:hover   { background: $hover; border-color: $border_strong; }
QPushButton:pressed { background: $pressed; }
QPushButton:focus   { border: 1px solid $accent; }
QPushButton:disabled { color: $muted; background: transparent; border-color: $border; }

QPushButton[variant="primary"] {
    background: $accent; color: $accent_text;
    border: 1px solid $accent;
    font-weight: 700; padding: 13px 20px; font-size: 14px;
    border-radius: 12px;
}
QPushButton[variant="primary"]:hover {
    background: $accent_hover; border-color: $accent_hover;
}
QPushButton[variant="primary"]:disabled {
    background: $accent_dim; color: $accent_dim_text; border-color: $accent_dim;
}

QPushButton[variant="danger"] {
    background: transparent; color: $danger; border-color: $danger_border;
}
QPushButton[variant="danger"]:hover {
    background: $danger_bg; border-color: $danger;
}

QPushButton[variant="ghost"] {
    background: transparent; border-color: transparent; color: $muted; padding: 6px 10px;
}
QPushButton[variant="ghost"]:hover { background: $hover; color: $text; }

QPushButton[variant="header"] {
    background: transparent;
    color: $muted;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 7px 12px;
    font-size: 13px;
    font-weight: 600;
    min-width: 0;
}
QPushButton[variant="header"]:hover {
    background: $surface2;
    border-color: $border;
    color: $text;
}
QPushButton[variant="header"][emphasis="1"] {
    background: $accent_dim;
    color: $accent_dim_text;
    border-color: $accent;
}
QPushButton[variant="header"][emphasis="1"]:hover {
    background: $accent;
    color: $accent_text;
    border-color: $accent;
}

/* ---------- Поля ввода ---------- */
QLineEdit {
    background: $surface2;
    border: 1px solid $border;
    border-radius: 11px;
    padding: 11px 14px;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QLineEdit:hover { border-color: $border_strong; }
QLineEdit:focus { border: 1px solid $accent; background: $surface; }

/* ---------- Статус загрузки IPA ---------- */
QFrame#downloadStatusPanel {
    background: $surface2;
    border: 1px solid $border;
    border-radius: 14px;
    padding: 4px;
}
QFrame#downloadStatusPanel[phase="running"] {
    border-color: $accent;
    background: $accent_dim;
}
QFrame#downloadStatusPanel[phase="ok"] {
    border-color: $ok_border;
    background: $ok_bg;
}
QFrame#downloadStatusPanel[phase="error"] {
    border-color: $danger_border;
    background: $danger_bg;
}
QFrame#downloadStatusPanel[phase="idle"] {
    border-color: $border;
}
QLabel#downloadStateTitle {
    font-size: 14px;
    font-weight: 700;
    color: $text;
}
QLabel#downloadStateTitle[phase="running"] { color: $accent; }
QLabel#downloadStateTitle[phase="ok"] { color: $ok; }
QLabel#downloadStateTitle[phase="error"] { color: $danger; }
QLabel#downloadStateDetail, QLabel#downloadProgressLabel {
    color: $muted;
    font-size: 13px;
    line-height: 1.4;
}
QProgressBar#downloadProgress {
    background: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    text-align: center;
    min-height: 20px;
    max-height: 20px;
    color: $text;
    font-size: 11px;
}
QProgressBar#downloadProgress::chunk {
    background: $accent;
    border-radius: 7px;
}

/* ---------- Журнал ---------- */
QPlainTextEdit#log {
    background: $log_bg;
    border: 1px solid $border;
    border-radius: 12px;
    padding: 12px;
    font-family: "Cascadia Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    color: $muted;
    selection-background-color: $accent;
    selection-color: $accent_text;
}

/* ---------- Скроллбары ---------- */
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical {
    background: $border_strong; border-radius: 4px; min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: $muted; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QToolTip {
    background: $surface2; color: $text;
    border: 1px solid $border_strong; padding: 6px 10px; border-radius: 8px;
}

/* ---------- Меню ---------- */
QMenu {
    background: $surface;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 12px;
    padding: 8px;
}
QMenu::item {
    background: transparent;
    color: $text;
    padding: 8px 18px;
    border-radius: 8px;
}
QMenu::item:selected {
    background: $accent_dim;
    color: $accent_dim_text;
}
QMenu::item:disabled {
    color: $muted;
}
QMenu::separator {
    height: 1px;
    background: $border;
    margin: 6px 10px;
}

QCheckBox {
    color: $text;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid $border_strong;
    border-radius: 5px;
    background: $surface2;
}
QCheckBox::indicator:checked {
    background: $accent;
    border-color: $accent;
}

/* ---------- Системные диалоги ---------- */
QMessageBox, QInputDialog {
    background-color: $surface;
    color: $text;
}
QMessageBox QLabel, QInputDialog QLabel {
    color: $text;
    background-color: transparent;
}
QMessageBox QPushButton, QInputDialog QPushButton {
    min-width: 80px;
    background: $surface2;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 9px;
    padding: 8px 14px;
}
QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {
    background: $hover;
    border-color: $accent;
}
QMessageBox QPushButton:default, QInputDialog QPushButton:default {
    background: $accent;
    color: $accent_text;
    border-color: $accent;
}
"""
)


def build_stylesheet(mode: str = "dark") -> str:
    return _QSS.substitute(PALETTES[mode])


def build_palette(mode: str = "dark") -> QPalette:
    """Fusion palette matching theme tokens — keeps QMessageBox/QMenu readable."""
    p = PALETTES[mode if mode in PALETTES else "dark"]
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(p["surface"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(p["text"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(p["surface2"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(p["surface"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(p["text"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(p["surface2"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(p["text"]))
    pal.setColor(QPalette.ColorRole.BrightText, QColor(p["text"]))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(p["surface2"]))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(p["text"]))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(p["muted"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(p["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(p["accent_text"]))
    pal.setColor(QPalette.ColorRole.Link, QColor(p["accent"]))
    return pal


def repolish(widget) -> None:
    """Пересчитать стиль после setProperty(...)."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
