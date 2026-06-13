"""Components namespace mapped to the existing components directory."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
__path__ = [str(_ROOT / "components"), str(Path(__file__).resolve().parent)]

try:
    from .collapsible_section import CollapsibleSection
except Exception:  # pragma: no cover - optional UI import
    CollapsibleSection = None  # type: ignore

try:
    from cerebro.ui.widgets.status_indicator import StatusIndicator
except Exception:  # pragma: no cover - optional UI import
    StatusIndicator = None  # type: ignore

__all__ = ["CollapsibleSection", "StatusIndicator"]
