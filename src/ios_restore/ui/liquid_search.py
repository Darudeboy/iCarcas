"""Focused Liquid Glass-inspired search surface for the restore workflow.

Pure presentation: callers own search, region selection and worker lifecycle.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton


class _FocusStyler(QObject):
    def __init__(self, surface: QFrame) -> None:
        super().__init__(surface)
        self.surface = surface

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.surface.setProperty(
                "searchFocus", event.type() == QEvent.Type.FocusIn
            )
            self.surface.style().unpolish(self.surface)
            self.surface.style().polish(self.surface)
        return False


class LiquidSearchBar(QFrame):
    """Search field, region picker and search action in one compact surface."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("liquidSearch")
        self.setProperty("searchFocus", False)
        self.setStyleSheet("""
            QFrame#liquidSearch {
                background: rgba(232, 241, 252, 225);
                border: 1px solid #CBDDF0;
                border-radius: 22px;
            }
            QFrame#liquidSearch[searchFocus="true"] {
                background: rgba(239, 248, 255, 245);
                border: 2px solid #278CC6;
            }
            QFrame#liquidSearch QLabel {
                border: none; background: transparent;
                color: #38738E; font-size: 20px;
            }
            QFrame#liquidSearch QLineEdit {
                border: none; background: transparent;
                padding: 9px 3px; font-size: 15px;
                color: #18374C; min-height: 28px;
            }
            QFrame#liquidSearch QComboBox {
                border: 1px solid #C5D8E9;
                border-radius: 13px;
                background: rgba(255,255,255,190);
                padding: 8px 12px;
                min-width: 85px;
                color: #24465A;
            }
            QFrame#liquidSearch QPushButton {
                border: none; border-radius: 14px;
                background: #07889B; color: white;
                font-weight: 700; padding: 11px 18px;
            }
            QFrame#liquidSearch QPushButton:hover {
                background: #086F88;
            }
            QFrame#liquidSearch QPushButton:disabled {
                background: #9DBCC5;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 9, 10, 9)
        layout.setSpacing(10)
        icon = QLabel("⌕", self)
        icon.setFixedWidth(25)
        layout.addWidget(icon)
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Название, App Store ID или Bundle ID")
        self.search_input.setClearButtonEnabled(True)
        layout.addWidget(self.search_input, 1)
        self.region_selector = QComboBox(self)
        self.region_selector.setToolTip("Регион App Store")
        layout.addWidget(self.region_selector)
        self.search_button = QPushButton("Найти", self)
        layout.addWidget(self.search_button)
        self._focus_styler = _FocusStyler(self)
        self.search_input.installEventFilter(self._focus_styler)
