"""Compatibility package for the flat source tree.

The uploaded application sources live at the repository root, while runtime
imports use the ``cerebro.*`` package namespace.  The subpackages in this
directory map those namespaces back to the existing files.
"""
from __future__ import annotations

__version__ = "5.0.0"

__all__ = ["__version__"]
