"""Диалог «Что нового» из CHANGELOG.md."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from ios_restore.infrastructure.paths import project_root


def changelog_path() -> Path:
    return project_root() / "CHANGELOG.md"


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
    # Minimal markdown → HTML for headings and lists.
    html_lines: list[str] = ["<h2>Что нового</h2>"]
    for line in body.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            html_lines.append(f"<h3>{line[3:].strip()}</h3>")
        elif line.startswith("- "):
            html_lines.append(f"<p>• {line[2:].strip()}</p>")
        elif line.strip():
            html_lines.append(f"<p>{line.strip()}</p>")
    return "\n".join(html_lines)


def show_release_notes_dialog(parent: QWidget | None = None) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Что нового")
    dialog.resize(520, 480)
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
