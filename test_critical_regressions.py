#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).parent


class _DummySignal:
    def __init__(self, *args, **kwargs):
        self.emissions = []

    def connect(self, *args, **kwargs):
        return None

    def emit(self, *args, **kwargs):
        self.emissions.append((args, kwargs))


class _DummyQtBase:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        def _method(*args, **kwargs):
            return None
        return _method


class _DummyQt:
    def __getattr__(self, name):
        return 0


def _slot(*args, **kwargs):
    def _decorator(func):
        return func
    return _decorator


def _load_module(name: str, path: Path):
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _install_fast_scan_stubs():
    py_side = types.ModuleType("PySide6")
    qt_core = types.ModuleType("PySide6.QtCore")
    qt_core.QThread = _DummyQtBase
    qt_core.QObject = _DummyQtBase
    qt_core.Signal = _DummySignal
    sys.modules["PySide6"] = py_side
    sys.modules["PySide6.QtCore"] = qt_core

    cerebro = sys.modules.setdefault("cerebro", types.ModuleType("cerebro"))
    core = types.ModuleType("cerebro.core")
    ui = types.ModuleType("cerebro.ui")
    state_bus = types.ModuleType("cerebro.ui.state_bus")
    models = types.ModuleType("cerebro.core.models")
    fast_pipeline = types.ModuleType("cerebro.core.fast_pipeline")

    class FakePipeline:
        calls = []

        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def cancel(self):
            return None

        def run_fast_scan(self, root, **kwargs):
            FakePipeline.calls.append((root, kwargs))
            return {
                "ok": True,
                "groups": [{"hash": "h1", "paths": ["/tmp/a", "/tmp/b", "/tmp/c"]}],
                "file_count": 3,
                "total_size": 9,
                "scan_duration": 0.1,
            }

    class FakeStateBus:
        @staticmethod
        def allowed_extensions_for_media_type(media_type):
            return []

    class FakeScanProgress:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    fast_pipeline.FastPipeline = FakePipeline
    state_bus.StateBus = FakeStateBus
    models.ScanProgress = FakeScanProgress

    cerebro.core = core
    sys.modules["cerebro.core"] = core
    sys.modules["cerebro.ui"] = ui
    sys.modules["cerebro.ui.state_bus"] = state_bus
    sys.modules["cerebro.core.models"] = models
    sys.modules["cerebro.core.fast_pipeline"] = fast_pipeline
    return FakePipeline


def _install_review_page_stubs():
    py_side = types.ModuleType("PySide6")
    qt_core = types.ModuleType("PySide6.QtCore")
    qt_gui = types.ModuleType("PySide6.QtGui")
    qt_widgets = types.ModuleType("PySide6.QtWidgets")

    qt_core.Qt = _DummyQt()
    qt_core.QSize = _DummyQtBase
    qt_core.QRect = _DummyQtBase
    qt_core.QPoint = _DummyQtBase
    qt_core.QEvent = _DummyQtBase
    qt_core.QTimer = _DummyQtBase
    qt_core.Signal = _DummySignal
    qt_core.Slot = _slot
    qt_core.QRunnable = _DummyQtBase
    qt_core.QThreadPool = _DummyQtBase
    qt_core.QObject = _DummyQtBase
    qt_core.QMutex = _DummyQtBase
    qt_core.QMutexLocker = _DummyQtBase
    qt_core.QPropertyAnimation = _DummyQtBase
    qt_core.QEasingCurve = _DummyQtBase
    qt_core.QItemSelectionModel = _DummyQtBase

    for name in ("QPixmap", "QKeySequence", "QShortcut", "QKeyEvent", "QFontMetrics", "QColor", "QPainter", "QFont"):
        setattr(qt_gui, name, _DummyQtBase)
    for name in (
        "QWidget", "QVBoxLayout", "QHBoxLayout", "QGridLayout", "QLayout",
        "QLabel", "QPushButton", "QFrame", "QScrollArea", "QSplitter",
        "QComboBox", "QCheckBox", "QDialog", "QListWidget", "QListWidgetItem",
        "QStackedWidget", "QSizePolicy", "QTableWidget", "QTableWidgetItem",
        "QHeaderView", "QAbstractItemView", "QMessageBox", "QInputDialog",
        "QProgressBar", "QTextEdit", "QGroupBox", "QToolButton",
        "QGraphicsDropShadowEffect", "QApplication",
    ):
        setattr(qt_widgets, name, _DummyQtBase)

    sys.modules["PySide6"] = py_side
    sys.modules["PySide6.QtCore"] = qt_core
    sys.modules["PySide6.QtGui"] = qt_gui
    sys.modules["PySide6.QtWidgets"] = qt_widgets

    for module_name in ("cerebro", "cerebro.ui", "cerebro.ui.pages"):
        sys.modules.setdefault(module_name, types.ModuleType(module_name))
    base_station = types.ModuleType("cerebro.ui.pages.base_station")
    base_station.BaseStation = _DummyQtBase
    state_bus = types.ModuleType("cerebro.ui.state_bus")
    state_bus.get_state_bus = lambda: _DummyQtBase()
    theme_engine = types.ModuleType("cerebro.ui.theme_engine")
    theme_engine.get_theme_manager = lambda: None
    sys.modules["cerebro.ui.pages.base_station"] = base_station
    sys.modules["cerebro.ui.state_bus"] = state_bus
    sys.modules["cerebro.ui.theme_engine"] = theme_engine


def _install_pipeline_stubs():
    for module_name in ("cerebro", "cerebro.core", "cerebro.history"):
        module = sys.modules.setdefault(module_name, types.ModuleType(module_name))
        module.__path__ = []

    deletion = types.ModuleType("cerebro.core.deletion")
    deletion.DeletionEngine = _DummyQtBase
    deletion.DeletionPolicy = _DummyQtBase
    deletion.DeletionRequest = _DummyQtBase
    deletion.BatchDeletionResult = _DummyQtBase
    history_store = types.ModuleType("cerebro.history.store")
    history_store.HistoryStore = _DummyQtBase
    sys.modules["cerebro.core.deletion"] = deletion
    sys.modules["cerebro.history.store"] = history_store


class CriticalRegressionTests(unittest.TestCase):
    def test_turbo_scan_uses_grouped_pipeline_payload(self):
        fake_pipeline = _install_fast_scan_stubs()
        module = _load_module("cerebro.workers.fast_scan_worker", ROOT / "fast_scan_worker.py")

        module.FastScanWorker.finished.emissions.clear()
        worker = module.FastScanWorker({"root": "/tmp", "scanner_tier": "turbo"})
        worker.run()

        self.assertEqual(len(fake_pipeline.calls), 1)
        payload = module.FastScanWorker.finished.emissions[-1][0][0]
        self.assertEqual(payload["group_count"], 1)
        self.assertEqual(payload["groups_found"], 1)
        self.assertEqual(payload["duplicate_count"], 2)
        self.assertEqual(payload["scanner_name"], "FastPipeline")

    def test_review_cleanup_groups_emit_keep_and_delete_intent(self):
        _install_review_page_stubs()
        module = _load_module("cerebro.ui.pages.review_page", ROOT / "pages" / "review_page.py")

        with tempfile.TemporaryDirectory() as tmp:
            keeper = Path(tmp) / "keep.txt"
            duplicate = Path(tmp) / "delete.txt"
            keeper.write_text("same")
            duplicate.write_text("same")

            group = module.GroupData(
                paths=[str(keeper), str(duplicate)],
                hint="same hash",
                group_id=42,
            )
            groups, total_size = module.build_cleanup_deletion_groups(
                [group],
                {42: {str(keeper): True, str(duplicate): False}},
            )

        self.assertEqual(total_size, 4)
        self.assertEqual(groups, [{
            "group_index": 42,
            "keep": str(keeper),
            "delete": [str(duplicate)],
            "hint": "same hash",
            "recoverable_bytes": 4,
        }])
        self.assertNotIn("paths", groups[0])

    def test_delete_plan_keeps_valid_operations_when_other_group_is_stale(self):
        _install_pipeline_stubs()
        module = _load_module("cerebro.core.pipeline", ROOT / "pipeline.py")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            keeper = tmp_path / "keep.txt"
            duplicate = tmp_path / "delete.txt"
            stale_keeper = tmp_path / "missing.txt"
            other_duplicate = tmp_path / "other.txt"
            keeper.write_text("same")
            duplicate.write_text("same")
            other_duplicate.write_text("other")

            pipeline = module.CerebroPipeline()
            plan = pipeline.build_delete_plan({
                "scan_id": "scan-1",
                "policy": {"mode": "trash"},
                "groups": [
                    {"group_index": 0, "keep": str(keeper), "delete": [str(duplicate)]},
                    {"group_index": 1, "keep": str(stale_keeper), "delete": [str(other_duplicate)]},
                ],
            })

        self.assertEqual(plan.total_files, 1)
        self.assertEqual(plan.operations[0].path, duplicate)
        self.assertEqual(plan.stats["validation_errors"], 1)


if __name__ == "__main__":
    unittest.main()
