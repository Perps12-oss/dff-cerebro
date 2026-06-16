from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path


class _BoundSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _Signal:
    def __init__(self, *args, **kwargs) -> None:
        self._name = None

    def __set_name__(self, owner, name) -> None:
        self._name = f"__signal_{name}"

    def __get__(self, instance, owner):
        if instance is None:
            return self
        signal = instance.__dict__.get(self._name)
        if signal is None:
            signal = _BoundSignal()
            instance.__dict__[self._name] = signal
        return signal


class _QObject:
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()


class _QtObject:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __getattr__(self, name):
        return _QtObject()

    def __call__(self, *args, **kwargs):
        return _QtObject()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _QThread(_QObject):
    def start(self) -> None:
        self.run()


class _QTimer(_QObject):
    timeout = _Signal()

    def setInterval(self, value) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class _QThreadPool(_QtObject):
    @staticmethod
    def globalInstance():
        return _QThreadPool()


def _install_pyside_stubs() -> None:
    pyside = sys.modules.setdefault("PySide6", types.ModuleType("PySide6"))
    qtcore = sys.modules.setdefault("PySide6.QtCore", types.ModuleType("PySide6.QtCore"))
    qtcore.QObject = _QObject
    qtcore.QThread = _QThread
    qtcore.Signal = _Signal
    qtcore.Slot = lambda *args, **kwargs: (lambda func: func)
    qtcore.QTimer = _QTimer
    qtcore.QRunnable = _QtObject
    qtcore.QThreadPool = _QThreadPool
    qtcore.QMutex = _QtObject
    qtcore.QMutexLocker = _QtObject
    qtcore.QPropertyAnimation = _QtObject
    qtcore.QItemSelectionModel = _QtObject
    qtcore.Qt = types.SimpleNamespace(
        Checked=2,
        Unchecked=0,
        AlignRight=1,
        AlignVCenter=2,
        AlignCenter=4,
        KeepAspectRatio=1,
        SmoothTransformation=1,
        ItemIsUserCheckable=1,
        CursorShape=types.SimpleNamespace(PointingHandCursor=1),
    )
    for name in ("QSize", "QRect", "QPoint", "QEvent", "QEasingCurve"):
        setattr(qtcore, name, _QtObject)

    qtgui = sys.modules.setdefault("PySide6.QtGui", types.ModuleType("PySide6.QtGui"))
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
        setattr(qtgui, name, _QtObject)

    qtwidgets = sys.modules.setdefault("PySide6.QtWidgets", types.ModuleType("PySide6.QtWidgets"))
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
        "QInputDialog",
        "QProgressBar",
        "QTextEdit",
        "QGroupBox",
        "QToolButton",
        "QGraphicsDropShadowEffect",
        "QApplication",
    ):
        setattr(qtwidgets, name, _QtObject)
    qtwidgets.QMessageBox = types.SimpleNamespace(Yes=1, No=2, warning=lambda *args, **kwargs: None)

    pyside.QtCore = qtcore
    pyside.QtGui = qtgui
    pyside.QtWidgets = qtwidgets


def _install_review_page_dependency_stubs() -> None:
    base_station = types.ModuleType("cerebro.ui.pages.base_station")
    base_station.BaseStation = _QtObject
    sys.modules["cerebro.ui.pages.base_station"] = base_station

    class _StateBus:
        @staticmethod
        def allowed_extensions_for_media_type(media_type: str):
            return None

    state_bus = types.ModuleType("cerebro.ui.state_bus")
    state_bus.StateBus = _StateBus
    state_bus.get_state_bus = lambda: types.SimpleNamespace(notify=lambda *args, **kwargs: None)
    sys.modules["cerebro.ui.state_bus"] = state_bus

    theme_engine = types.ModuleType("cerebro.ui.theme_engine")
    theme_engine.get_theme_manager = lambda: None
    sys.modules["cerebro.ui.theme_engine"] = theme_engine


class CriticalRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        _install_pyside_stubs()

    def test_cerebro_namespace_resolves_flat_modules(self) -> None:
        import cerebro
        import cerebro.services.hash_cache as hash_cache

        self.assertEqual(cerebro.__version__, "5.0.0")
        self.assertTrue(hasattr(hash_cache, "HashCache"))

    def test_live_scan_snapshot_can_record_failure(self) -> None:
        from cerebro.ui.models.live_scan_snapshot import LiveScanSnapshot, ScanPhase

        snapshot = LiveScanSnapshot()
        snapshot.start_scan("scan-1")
        snapshot.fail_scan("boom")

        self.assertEqual(snapshot.phase, ScanPhase.FAILED)
        self.assertFalse(snapshot.is_active)
        self.assertEqual(snapshot.current_operation, "Failed")
        self.assertEqual(snapshot.warnings_count, 1)

    def test_turbo_worker_uses_grouping_pipeline(self) -> None:
        from cerebro.workers.fast_scan_worker import FastScanWorker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"duplicate-content" * 128
            (root / "a.bin").write_bytes(payload)
            (root / "b.bin").write_bytes(payload)
            (root / "unique.bin").write_bytes(b"unique-content" * 128)

            worker = FastScanWorker({
                "root": str(root),
                "scanner_tier": "turbo",
                "min_size_bytes": 1,
                "include_hidden": True,
            })
            finished = []
            failed = []
            worker.finished.connect(finished.append)
            worker.failed.connect(failed.append)

            worker.run()

            self.assertEqual(failed, [])
            self.assertEqual(len(finished), 1)
            groups = finished[0].get("groups") or []
            self.assertEqual(len(groups), 1)
            self.assertCountEqual([Path(p).name for p in groups[0]["paths"]], ["a.bin", "b.bin"])
            self.assertEqual(finished[0].get("group_count"), 1)

    def test_review_cleanup_payload_uses_deletion_plan_contract(self) -> None:
        _install_review_page_dependency_stubs()
        from cerebro.ui.pages.review_page import GroupData, build_deletion_plan_from_groups

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            keep = root / "keep.bin"
            delete = root / "delete.bin"
            keep.write_bytes(b"keep")
            delete.write_bytes(b"delete-me")

            group = GroupData(paths=[str(keep), str(delete)], hint="same hash", group_id=7)
            plan = build_deletion_plan_from_groups(
                [group],
                {7: {str(keep): True, str(delete): False}},
                scan_id="scan-123",
            )

        self.assertEqual(plan["scan_id"], "scan-123")
        self.assertEqual(plan["policy"], {"mode": "trash"})
        self.assertEqual(plan["source"], "review_page")
        self.assertEqual(plan["stats"]["group_count"], 1)
        self.assertEqual(plan["stats"]["file_count"], 1)
        self.assertEqual(plan["groups"], [{
            "group_index": 7,
            "keep": str(keep),
            "delete": [str(delete)],
            "hint": "same hash",
            "recoverable_bytes": len(b"delete-me"),
        }])
        self.assertNotIn("paths", plan["groups"][0])


if __name__ == "__main__":
    unittest.main()
