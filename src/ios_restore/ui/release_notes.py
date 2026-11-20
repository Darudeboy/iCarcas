"""Диалог «Что нового» из CHANGELOG.md."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from ios_restore.infrastructure.paths import project_root


def changelog_path() -> Path:
    return project_root() / "CHANGELOG.md"


def _inline_md(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


def load_changelog_html(limit_sections: int = 3) -> str:
    path = changelog_path()
    if not path.is_file():
        return "<p>Файл CHANGELOG.md не найден.</p>"
    text = path.read_text(encoding="utf-8")
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("## ") and current:
            sections.append("\n".join(current))
            current = [line]
            if len(sections) >= limit_sections:
                break
        else:
            current.append(line)
    if current and len(sections) < limit_sections:
        sections.append("\n".join(current))
    body = "\n\n".join(sections) if sections else text

    html_lines: list[str] = [
        "<style>"
        "body { font-family: 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.45; }"
        "h2 { margin: 0 0 12px 0; font-size: 18px; }"
        "h3 { margin: 18px 0 8px 0; font-size: 15px; }"
        "h4 { margin: 14px 0 6px 0; font-size: 14px; }"
        "p { margin: 0 0 10px 0; }"
        "ul { margin: 0 0 12px 18px; padding: 0; }"
        "li { margin: 0 0 6px 0; }"
        "</style>",
        "<h2>Что нового</h2>",
    ]
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            html_lines.append("</ul>")
            in_list = False

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            continue
        if stripped.startswith("### "):
            close_list()
            html_lines.append(f"<h4>{_inline_md(stripped[4:])}</h4>")
        elif stripped.startswith("## "):
            close_list()
            html_lines.append(f"<h3>{_inline_md(stripped[3:])}</h3>")
        elif stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_inline_md(stripped[2:])}</li>")
        elif stripped:
            close_list()
            html_lines.append(f"<p>{_inline_md(stripped)}</p>")
        else:
            close_list()
    close_list()
    return "\n".join(html_lines)


def show_release_notes_dialog(parent: QWidget | None = None) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Что нового")
    dialog.resize(560, 560)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser(dialog)
    browser.setOpenExternalLinks(True)
    browser.setHtml(load_changelog_html())
    layout.addWidget(browser)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    buttons.clicked.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()
