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


class _QThread(_QObject):
    def start(self) -> None:
        self.run()


def _install_pyside_stubs() -> None:
    if "PySide6" in sys.modules:
        return
    pyside = types.ModuleType("PySide6")
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = _QObject
    qtcore.QThread = _QThread
    qtcore.Signal = _Signal
    qtcore.Slot = lambda *args, **kwargs: (lambda func: func)
    qtcore.QTimer = type("QTimer", (_QObject,), {"setInterval": lambda self, value: None, "start": lambda self: None, "stop": lambda self: None, "timeout": _Signal()})
    qtcore.Qt = types.SimpleNamespace()
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qtcore


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


if __name__ == "__main__":
    unittest.main()
