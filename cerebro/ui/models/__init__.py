"""UI models namespace mapped to the existing models directory."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
__path__ = [str(_ROOT / "models")]
