"""Theme token helpers for modern UI components."""
from __future__ import annotations

from typing import Any

SPACE_UNIT = 8
RADIUS_MD = 12
SIDEBAR_WIDTH = 240
HEADER_HEIGHT = 72
STICKY_BAR_HEIGHT = 72

_DEFAULTS = {
    "bg": "#0f1115",
    "panel": "#171a21",
    "line": "#2a2f3a",
    "text": "#e5e7eb",
    "muted": "#9ca3af",
    "accent": "#3b82f6",
    "danger": "#ef4444",
}


def token(name: str, fallback: Any = None) -> str:
    """Return a theme color token with a stable fallback."""
    try:
        from cerebro.ui.theme_engine import current_colors

        colors = current_colors()
        value = colors.get(name)
        if value:
            return str(value)
    except Exception:
        pass
    return str(_DEFAULTS.get(name, fallback if fallback is not None else ""))
