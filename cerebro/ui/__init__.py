"""UI namespace mapped to root-level UI modules."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
__path__ = [str(_ROOT), str(Path(__file__).resolve().parent)]
