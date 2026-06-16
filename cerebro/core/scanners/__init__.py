"""Scanner namespace mapped to root-level scanner modules."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
__path__ = [str(_ROOT)]
