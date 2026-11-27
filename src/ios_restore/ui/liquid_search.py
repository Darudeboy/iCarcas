"""Compact search surface for the iCarcas restore workflow.

Keep the standard Qt combo popup painting: custom paint with transparent
foreground made Windows popup entries invisible.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy


class LiquidSearchBar(QFrame):
    """Unified, restrained App Store-style search with a working region selector."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("restoreSearch")
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("""
            QFrame#restoreSearch {
                background: #FFFFFF;
                border: 1px solid #D9E3EC;
                border-radius: 17px;
            }
            QFrame#restoreSearch:focus-within {
                border-color: #9BBECD;
            }
            QFrame#restoreSearch QLabel {
                border: none; background: transparent;
                color: #647E90; font-size: 19px;
            }
            QFrame#restoreSearch QLineEdit {
                background: transparent; border: none;
                color: #17364C; font-size: 14px;
                padding: 3px 0;
            }
            QFrame#restoreSearch QComboBox {
                background: #F1F5F8;
                border: 1px solid #E1E9EF;
                border-radius: 12px;
                padding: 7px 12px;
                color: #17364C;
                font-size: 13px;
                min-width: 62px;
            }
            QFrame#restoreSearch QComboBox::drop-down {
                border: none; width: 20px;
            }
            QFrame#restoreSearch QComboBox QAbstractItemView {
                background: #FFFFFF;
                color: #17364C;
                border: 1px solid #D9E3EC;
                selection-background-color: #E5F3F6;
                selection-color: #087B89;
                padding: 5px;
                outline: 0;
            }
            QFrame#restoreSearch QPushButton {
                color: white; font-weight: 700;
                border: none; border-radius: 12px;
                background: #087F91;
                padding: 8px 18px;
            }
            QFrame#restoreSearch QPushButton:hover {
                background: #076B7B;
            }
            QFrame#restoreSearch QPushButton:disabled {
                background: #A8C6CC; color: #F5FAFB;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 7, 7, 7)
        layout.setSpacing(10)
        icon = QLabel("⌕", self)
        icon.setFixedWidth(22)
        layout.addWidget(icon)
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Название, Store ID или Bundle ID")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(0)
        layout.addWidget(self.search_input, 1)
        self.region_selector = QComboBox(self)
        self.region_selector.setToolTip("Регион App Store")
        self.region_selector.setFixedWidth(104)
        self.region_selector.setFixedHeight(39)
        self.region_selector.setMaxVisibleItems(12)
        layout.addWidget(self.region_selector)
        self.search_button = QPushButton("Найти", self)
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.setFixedHeight(40)
        self.search_button.setMinimumWidth(86)
        layout.addWidget(self.search_button)
