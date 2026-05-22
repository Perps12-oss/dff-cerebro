#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path


class _Signal:
    def __init__(self, *args, **kwargs):
        self._emitted = []

    def connect(self, *args, **kwargs):
        return None

    def emit(self, *args, **kwargs):
        self._emitted.append((args, kwargs))


class _Dummy:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return _Dummy()

    def __getattr__(self, name):
        return _Dummy()


class _Qt:
    def __getattr__(self, name):
        return 0


def _slot(*args, **kwargs):
    def decorator(fn):
        return fn

    return decorator


def _install_qt_stubs() -> None:
    pyside6 = types.ModuleType("PySide6")
    qtcore = types.ModuleType("PySide6.QtCore")
    qtgui = types.ModuleType("PySide6.QtGui")
    qtwidgets = types.ModuleType("PySide6.QtWidgets")

    qtcore.Qt = _Qt()
    qtcore.Signal = lambda *args, **kwargs: _Signal(*args, **kwargs)
    qtcore.Slot = _slot
    for name in (
        "QItemSelectionModel",
        "QSize",
        "QRect",
        "QPoint",
        "QEvent",
        "QTimer",
        "QRunnable",
        "QThreadPool",
        "QObject",
        "QMutex",
        "QMutexLocker",
        "QPropertyAnimation",
        "QEasingCurve",
    ):
        setattr(qtcore, name, _Dummy)

    for name in (
        "QPixmap",
        "QKeySequence",
        "QShortcut",
        "QKeyEvent",
        "QFontMetrics",
        "QColor",
        "QPainter",
        "QFont",
    ):
        setattr(qtgui, name, _Dummy)

    for name in (
        "QWidget",
        "QVBoxLayout",
        "QHBoxLayout",
        "QGridLayout",
        "QLayout",
        "QLabel",
        "QPushButton",
        "QFrame",
        "QScrollArea",
        "QSplitter",
        "QComboBox",
        "QCheckBox",
        "QDialog",
        "QListWidget",
        "QListWidgetItem",
        "QStackedWidget",
        "QSizePolicy",
        "QTableWidget",
        "QTableWidgetItem",
        "QHeaderView",
        "QAbstractItemView",
        "QMessageBox",
        "QInputDialog",
        "QProgressBar",
        "QTextEdit",
        "QGroupBox",
        "QToolButton",
        "QGraphicsDropShadowEffect",
        "QApplication",
    ):
        setattr(qtwidgets, name, _Dummy)

    sys.modules.setdefault("PySide6", pyside6)
    sys.modules.setdefault("PySide6.QtCore", qtcore)
    sys.modules.setdefault("PySide6.QtGui", qtgui)
    sys.modules.setdefault("PySide6.QtWidgets", qtwidgets)


def _install_cerebro_stubs() -> None:
    for name in (
        "cerebro",
        "cerebro.ui",
        "cerebro.ui.pages",
        "cerebro.ui.state_bus",
        "cerebro.ui.theme_engine",
        "cerebro.ui.pages.base_station",
    ):
        sys.modules.setdefault(name, types.ModuleType(name))

    base_station = sys.modules["cerebro.ui.pages.base_station"]
    base_station.BaseStation = _Dummy

    state_bus = sys.modules["cerebro.ui.state_bus"]
    state_bus.get_state_bus = lambda: _Dummy()

    theme_engine = sys.modules["cerebro.ui.theme_engine"]
    theme_engine.get_theme_manager = lambda: None


def _load_review_page_module():
    _install_qt_stubs()
    _install_cerebro_stubs()
    module_path = Path(__file__).resolve().parent / "pages" / "review_page.py"
    spec = importlib.util.spec_from_file_location("review_page_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReviewCleanupPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review_page = _load_review_page_module()

    def test_cleanup_payload_uses_keep_delete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            keeper = root / "keeper.txt"
            duplicate_a = root / "duplicate-a.txt"
            duplicate_b = root / "duplicate-b.txt"
            keeper.write_text("keep", encoding="utf-8")
            duplicate_a.write_text("aaaa", encoding="utf-8")
            duplicate_b.write_text("bbbbbb", encoding="utf-8")

            group = self.review_page.GroupData(
                paths=[str(duplicate_a), str(keeper), str(duplicate_b)],
                hint="same hash",
                group_id=42,
            )
            payload = self.review_page.build_cleanup_payload(
                [group],
                {42: {str(duplicate_a): False, str(keeper): True, str(duplicate_b): False}},
                scan_id="scan-123",
            )

        self.assertEqual(payload["scan_id"], "scan-123")
        self.assertEqual(payload["policy"], {"mode": "trash"})
        self.assertEqual(payload["source"], "review_page")
        self.assertEqual(payload["stats"]["group_count"], 1)
        self.assertEqual(payload["stats"]["file_count"], 2)
        self.assertEqual(payload["stats"]["recoverable_bytes"], 10)
        self.assertEqual(payload["groups"][0]["group_index"], 42)
        self.assertEqual(payload["groups"][0]["keep"], str(keeper))
        self.assertEqual(payload["groups"][0]["delete"], [str(duplicate_a), str(duplicate_b)])
        self.assertNotIn("paths", payload["groups"][0])

    def test_cleanup_payload_rejects_all_delete_group(self):
        group = self.review_page.GroupData(paths=["/tmp/a", "/tmp/b"], group_id=7)
        with self.assertRaisesRegex(ValueError, "keep at least one file"):
            self.review_page.build_cleanup_payload(
                [group],
                {7: {"/tmp/a": False, "/tmp/b": False}},
            )


if __name__ == "__main__":
    unittest.main()
