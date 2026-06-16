"""Modern UI component exports."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_ROOT = Path(__file__).resolve().parents[4]
__path__ = [str(Path(__file__).resolve().parent), str(_ROOT / "components" / "modern")]

from ._tokens import RADIUS_MD, SPACE_UNIT, token
from .content_card import ContentCard
from .folder_picker import ModernFolderPicker
from .history_card import HistoryCard
from .page_header import PageHeader
from .page_scaffold import PageScaffold


def _pointing_hand_cursor():
    return getattr(getattr(Qt, "CursorShape", Qt), "PointingHandCursor", getattr(Qt, "PointingHandCursor", None))


class StatCard(QFrame):
    """Small metric card with a title and mutable value."""

    def __init__(self, title: str, value: str = "", icon: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_UNIT * 2, SPACE_UNIT * 2, SPACE_UNIT * 2, SPACE_UNIT * 2)
        layout.setSpacing(SPACE_UNIT)

        label_text = f"{icon} {title}" if icon else title
        self._title = QLabel(label_text)
        self._title.setObjectName("statCardTitle")
        self._value = QLabel(str(value))
        self._value.setObjectName("statCardValue")
        layout.addWidget(self._title)
        layout.addWidget(self._value)
        self._apply_theme()

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"""
            StatCard {{
                background: {token('panel')};
                border: 1px solid {token('line')};
                border-radius: {RADIUS_MD}px;
            }}
            QLabel#statCardTitle {{ color: {token('muted')}; font-size: 12px; }}
            QLabel#statCardValue {{ color: {token('text')}; font-size: 22px; font-weight: 700; }}
        """)

    def set_value(self, value: str) -> None:
        self._value.setText(str(value))


class StickyActionBar(QFrame):
    """Bottom action bar with summary text and primary/secondary actions."""

    primary_clicked = Signal()
    secondary_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("StickyActionBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_UNIT * 2)

        self._summary = QLabel("")
        self._summary.setObjectName("stickySummary")
        layout.addWidget(self._summary, 1)

        self._secondary = QPushButton("Cancel")
        self._secondary.clicked.connect(self.secondary_clicked.emit)
        cursor = _pointing_hand_cursor()
        if cursor is not None:
            self._secondary.setCursor(cursor)
        layout.addWidget(self._secondary)

        self._primary = QPushButton("Start")
        self._primary.clicked.connect(self.primary_clicked.emit)
        if cursor is not None:
            self._primary.setCursor(cursor)
        layout.addWidget(self._primary)
        self._apply_theme()

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"""
            StickyActionBar {{ background: transparent; }}
            QLabel#stickySummary {{ color: {token('text')}; font-weight: 600; }}
            QPushButton {{
                padding: 10px 18px;
                border-radius: {RADIUS_MD}px;
                color: {token('text')};
                border: 1px solid {token('line')};
            }}
        """)

    def set_summary(self, title: str, detail: str = "") -> None:
        self._summary.setText(f"{title}  {detail}".strip())

    def set_primary_text(self, text: str) -> None:
        self._primary.setText(text)

    def set_secondary_text(self, text: str) -> None:
        self._secondary.setText(text)

    def set_primary_enabled(self, enabled: bool) -> None:
        self._primary.setEnabled(bool(enabled))

    def set_secondary_enabled(self, enabled: bool) -> None:
        self._secondary.setEnabled(bool(enabled))


class ThemeCard(QFrame):
    """Clickable theme preview card."""

    clicked = Signal(str)

    def __init__(
        self,
        key: str,
        name: str,
        colors: Iterable[str],
        *,
        active: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._key = key
        self._active = bool(active)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_UNIT * 2, SPACE_UNIT * 2, SPACE_UNIT * 2, SPACE_UNIT * 2)
        layout.setSpacing(SPACE_UNIT)
        self._name = QLabel(name)
        layout.addWidget(self._name)
        swatches = QHBoxLayout()
        for color in list(colors)[:4]:
            swatch = QFrame()
            swatch.setFixedSize(24, 24)
            swatch.setStyleSheet(f"background: {color or token('panel')}; border-radius: 4px;")
            swatches.addWidget(swatch)
        swatches.addStretch(1)
        layout.addLayout(swatches)
        self.setCursor(_pointing_hand_cursor())
        self.set_active(active)

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        border = token("accent") if self._active else token("line")
        self.setStyleSheet(f"""
            ThemeCard {{
                background: {token('panel')};
                border: 2px solid {border};
                border-radius: {RADIUS_MD}px;
            }}
            QLabel {{ color: {token('text')}; font-weight: 600; }}
        """)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._key)
        super().mousePressEvent(event)


@dataclass(frozen=True)
class SidebarNavItem:
    item_id: str
    icon: str
    label: str
    badge_count: int = 0


class SidebarNav(QFrame):
    """Vertical navigation list for settings sections."""

    item_clicked = Signal(str)

    def __init__(self, items: Iterable[SidebarNavItem], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_UNIT)
        cursor = _pointing_hand_cursor()
        for item in items:
            text = f"{item.icon}  {item.label}"
            if item.badge_count:
                text = f"{text} ({item.badge_count})"
            button = QPushButton(text)
            button.setObjectName("SidebarNavButton")
            if cursor is not None:
                button.setCursor(cursor)
            button.clicked.connect(lambda _checked=False, item_id=item.item_id: self.item_clicked.emit(item_id))
            layout.addWidget(button)
            self._buttons[item.item_id] = button
        layout.addStretch(1)
        self.set_active("")

    def set_active(self, item_id: str) -> None:
        for key, button in self._buttons.items():
            active = key == item_id
            button.setProperty("active", active)
            button.setStyleSheet(f"""
                QPushButton#SidebarNavButton {{
                    text-align: left;
                    padding: 10px 12px;
                    border-radius: {RADIUS_MD}px;
                    color: {token('text')};
                    background: {token('accent') if active else 'transparent'};
                    border: 1px solid {token('line') if not active else token('accent')};
                }}
            """)


__all__ = [
    "ContentCard",
    "HistoryCard",
    "ModernFolderPicker",
    "PageHeader",
    "PageScaffold",
    "SidebarNav",
    "SidebarNavItem",
    "StatCard",
    "StickyActionBar",
    "ThemeCard",
]
