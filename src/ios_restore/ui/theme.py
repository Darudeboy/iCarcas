"""iCarcas light UI theme."""

from __future__ import annotations

COLORS = {
    "bg0": "#F5F7FA",
    "bg1": "#E9EEF4",
    "surface": "#FFFFFF",
    "ink": "#121417",
    "muted": "#6B7380",
    "line": "#D7DEE7",
    "accent": "#1A73E8",
    "danger": "#C62828",
    "danger_bg": "#FFF5F5",
}


STYLESHEET = f"""
QMainWindow, QWidget#centralRoot {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {COLORS["bg0"]},
        stop:1 {COLORS["bg1"]}
    );
    color: {COLORS["ink"]};
    font-family: "Segoe UI", sans-serif;
    font-size: 14px;
}}

QLabel#brandTitle {{
    font-family: "Segoe UI", sans-serif;
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -1px;
    color: {COLORS["ink"]};
    padding: 0;
    margin: 0;
}}

QLabel#brandTagline {{
    color: {COLORS["muted"]};
    font-size: 13px;
}}

QLabel#sectionLabel {{
    color: {COLORS["muted"]};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
}}

QFrame#panel {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["line"]};
    border-radius: 12px;
}}

QLineEdit#appInput {{
    background: #F7F9FC;
    border: 1px solid {COLORS["line"]};
    border-radius: 8px;
    padding-left: 10px;
    padding-right: 10px;
    font-size: 13px;
    color: {COLORS["ink"]};
}}
QLineEdit#appInput:focus {{
    border: 1px solid {COLORS["accent"]};
    background: #FFFFFF;
}}

QPushButton {{
    background: #FFFFFF;
    border: 1px solid {COLORS["line"]};
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    color: {COLORS["ink"]};
}}
QPushButton:hover {{
    background: #F3F6FA;
    border-color: #B9C4D1;
}}
QPushButton:pressed {{
    background: #E8EEF5;
}}
QPushButton:disabled {{
    color: #5C6670;
    background: #EEF1F4;
    border-color: #D5DCE5;
}}

QPushButton#primaryButton {{
    background: {COLORS["accent"]};
    border: 1px solid {COLORS["accent"]};
    color: #FFFFFF;
}}
QPushButton#primaryButton:hover {{
    background: #155FBF;
    border-color: #155FBF;
    color: #FFFFFF;
}}
QPushButton#primaryButton:pressed {{
    background: #124E9C;
    color: #FFFFFF;
}}
QPushButton#primaryButton:disabled {{
    background: #D9E3F0;
    border-color: #B0BECF;
    color: #1A2330;
}}

QPushButton#dangerButton {{
    color: {COLORS["danger"]};
    border-color: #F0B8B8;
    background: {COLORS["danger_bg"]};
}}
QPushButton#dangerButton:hover {{
    background: #FFE8E8;
    border-color: {COLORS["danger"]};
}}

QTextEdit#logView {{
    background: #F7F9FC;
    border: 1px solid {COLORS["line"]};
    border-radius: 8px;
    padding: 8px 10px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    color: {COLORS["ink"]};
}}
"""
