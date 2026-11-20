"""Тема iCarcas: токены + QSS. Подключается одной строкой:

    app.setStyleSheet(build_stylesheet("dark"))   # или "light"

Кнопки и метки получают вид через objectName и динамические свойства:
    QPushButton            -> обычная кнопка
    setProperty("variant", "primary" | "danger" | "ghost")
    QFrame#card            -> карточка
    QLabel#stepBadge       -> кружок шага, property state = idle | active | done
    QLabel#chip            -> плашка статуса, property state = idle | ok
    QToolButton#cornerChip -> угол: iOS / сессия
    QLabel#privacyNotice   -> локальное хранение УЗ
    QPlainTextEdit#log     -> журнал
"""
from __future__ import annotations

from string import Template

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#0F1117", "surface": "#171A22", "surface2": "#1E222C",
        "hover": "#262B37", "pressed": "#2E3441",
        "border": "#272C38", "border_strong": "#3A4152",
        "text": "#E8EAF0", "muted": "#A0A8BA",
        "accent": "#5B8DEF", "accent_hover": "#7AA3F5", "accent_text": "#0B1220",
        "accent_dim": "#243252", "accent_dim_text": "#7C8DB5",
        "danger": "#F27D7D", "danger_bg": "#2A1A1E", "danger_border": "#5A2D35",
        "ok": "#5FD3A0", "ok_bg": "#14291F", "ok_border": "#24523C",
        "log_bg": "#0B0D12",
    },
    "light": {
        "bg": "#F3F4F8", "surface": "#FFFFFF", "surface2": "#F4F5F9",
        "hover": "#E9ECF3", "pressed": "#DFE3EC",
        "border": "#E1E4EC", "border_strong": "#C8CEDB",
        "text": "#171A22", "muted": "#4F5668",
        "accent": "#2F6BFF", "accent_hover": "#4B80FF", "accent_text": "#FFFFFF",
        "accent_dim": "#C9D6F7", "accent_dim_text": "#6F83B8",
        "danger": "#D6404B", "danger_bg": "#FDEEEF", "danger_border": "#F2B8BD",
        "ok": "#1B8A5A", "ok_bg": "#E4F5EC", "ok_border": "#A9DCC3",
        "log_bg": "#F7F8FB",
    },
}

_QSS = Template(
    """
* {
    font-family: "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 14px;
    color: $text;
}
QWidget#root { background: $bg; }
QScrollArea#mainScroll { background: $bg; border: none; }
QScrollArea#mainScroll > QWidget > QWidget { background: $bg; }

/* ---------- Заголовок ---------- */
QLabel#appTitle { font-size: 28px; font-weight: 700; }
QLabel#appSubtitle {
    color: $muted;
    font-size: 14px;
    line-height: 1.35;
}
QLabel#hint {
    color: $muted;
    font-size: 13px;
    line-height: 1.4;
}

/* ---------- Карточки ---------- */
QFrame#card {
    background: $surface;
    border: 1px solid $border;
    border-radius: 16px;
}
QLabel#cardTitle { font-size: 16px; font-weight: 600; }
QLabel#cardStatus { color: $muted; font-size: 13px; }

/* ---------- Шаги ---------- */
QLabel#stepBadge {
    min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px;
    border-radius: 13px;
    background: $surface2; color: $muted;
    border: 1px solid $border_strong;
    font-weight: 600; font-size: 12px;
}
QLabel#stepBadge[state="active"] { background: $accent; color: $accent_text; border-color: $accent; }
QLabel#stepBadge[state="done"]   { background: $ok_bg; color: $ok; border-color: $ok_border; }

/* ---------- Плашки статуса ---------- */
QLabel#chip {
    background: $surface; color: $muted;
    border: 1px solid $border; border-radius: 12px;
    padding: 4px 12px; font-size: 12px;
}
QLabel#chip[state="ok"] { background: $ok_bg; color: $ok; border-color: $ok_border; }

QToolButton#cornerChip {
    background: $surface; color: $muted;
    border: 1px solid $border; border-radius: 12px;
    padding: 6px 14px; font-size: 13px; font-weight: 600;
    min-width: 88px;
}
QToolButton#cornerChip[state="ok"],
QToolButton#cornerChip[state="busy"] {
    background: $ok_bg; color: $ok; border-color: $ok_border;
}
QToolButton#cornerChip:hover { background: $hover; border-color: $border_strong; }
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
    font-size: 13px;
    line-height: 1.4;
    padding: 2px 2px 6px 2px;
}
QLabel#helpBody {
    color: $text;
    font-size: 14px;
    line-height: 1.45;
}

QPushButton#regionTag {
    background: $surface; color: $muted;
    border: 1px solid $border; border-radius: 12px;
    padding: 6px 10px; font-size: 12px; font-weight: 600;
}
QPushButton#regionTag[state="ok"] {
    background: $ok_bg; color: $ok; border-color: $ok_border;
}
QPushButton#regionTag:hover {
    background: $hover; border-color: $border_strong;
}
QPushButton#regionTag[state="ok"]:hover {
    background: $ok_bg; color: $ok; border-color: $ok;
}
QPushButton#regionTag:disabled {
    color: $muted; background: transparent;
}
QPushButton#regionTag[state="ok"]:disabled {
    background: $ok_bg; color: $ok; border-color: $ok_border;
}

/* ---------- Кнопки ---------- */
QPushButton {
    background: $surface2;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 10px 16px;
    font-weight: 500;
}
QPushButton:hover   { background: $hover; border-color: $border_strong; }
QPushButton:pressed { background: $pressed; }
QPushButton:focus   { border: 1px solid $accent; }
QPushButton:disabled { color: $muted; background: transparent; border-color: $border; }

QPushButton[variant="primary"] {
    background: $accent; color: $accent_text;
    border: 1px solid $accent;
    font-weight: 600; padding: 13px 20px; font-size: 14px;
}
QPushButton[variant="primary"]:hover    { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:disabled { background: $accent_dim; color: $accent_dim_text; border-color: $accent_dim; }

QPushButton[variant="danger"] { background: transparent; color: $danger; border-color: $danger_border; }
QPushButton[variant="danger"]:hover { background: $danger_bg; border-color: $danger; }

QPushButton[variant="ghost"] { background: transparent; border-color: transparent; color: $muted; padding: 6px 10px; }
QPushButton[variant="ghost"]:hover { background: $hover; color: $text; }

/* ---------- Поля ввода ---------- */
QLineEdit {
    background: $surface2;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 10px 12px;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QLineEdit:hover { border-color: $border_strong; }
QLineEdit:focus { border: 1px solid $accent; }

/* ---------- Статус загрузки IPA ---------- */
QFrame#downloadStatusPanel {
    background: $surface2;
    border: 1px solid $border;
    border-radius: 12px;
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
    min-height: 22px;
    max-height: 22px;
    color: $text;
    font-size: 12px;
}
QProgressBar#downloadProgress::chunk {
    background: $accent;
    border-radius: 7px;
}

/* ---------- Журнал ---------- */
QPlainTextEdit#log {
    background: $log_bg;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 10px;
    font-family: "Cascadia Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 13px;
    color: $muted;
    selection-background-color: $accent;
    selection-color: $accent_text;
}

/* ---------- Скроллбары ---------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border_strong; border-radius: 3px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: $muted; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QToolTip { background: $surface2; color: $text; border: 1px solid $border_strong; padding: 4px 8px; }
"""
)


def build_stylesheet(mode: str = "dark") -> str:
    return _QSS.substitute(PALETTES[mode])


def repolish(widget) -> None:
    """Пересчитать стиль после setProperty(...)."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
