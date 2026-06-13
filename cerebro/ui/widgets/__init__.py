"""Widgets namespace mapped to the existing widgets directory."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
__path__ = [str(_ROOT / "widgets"), str(_ROOT)]
