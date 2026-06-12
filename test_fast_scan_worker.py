#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


class _BoundSignal:
    def __init__(self) -> None:
        self.emissions = []
        self._slots = []

    def connect(self, slot) -> None:
        self._slots.append(slot)

    def emit(self, *args) -> None:
        self.emissions.append(args)
        for slot in list(self._slots):
            slot(*args)


class _SignalDescriptor:
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


def _signal(*_args, **_kwargs):
    return _SignalDescriptor()


class _QThread:
    def __init__(self, *_args, **_kwargs) -> None:
        pass


class _QObject:
    pass


class _ScanProgress:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class _StateBus:
    @staticmethod
    def allowed_extensions_for_media_type(_media_type):
        return []


class _RecordingPipeline:
    instances = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.run_calls = []
        self.cancelled = False
        self.__class__.instances.append(self)

    def cancel(self) -> None:
        self.cancelled = True

    def run_fast_scan(self, root, **kwargs):
        self.run_calls.append((root, kwargs))
        progress_cb = kwargs.get("progress_cb")
        if progress_cb:
            progress_cb(100, "done", {"phase": "completed", "groups_found": 1, "files_scanned": 2})
        return {
            "ok": True,
            "groups": [{"hash": "same", "paths": ["/tmp/a.txt", "/tmp/b.txt"], "count": 2}],
            "stats": {"files_scanned": 2},
        }


def _install_import_stubs() -> None:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QThread = _QThread
    qtcore.QObject = _QObject
    qtcore.Signal = _signal

    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qtcore

    fast_pipeline = types.ModuleType("cerebro.core.fast_pipeline")
    fast_pipeline.FastPipeline = _RecordingPipeline

    models = types.ModuleType("cerebro.core.models")
    models.ScanProgress = _ScanProgress

    state_bus = types.ModuleType("cerebro.ui.state_bus")
    state_bus.StateBus = _StateBus

    for name in [
        "cerebro",
        "cerebro.core",
        "cerebro.ui",
    ]:
        sys.modules.setdefault(name, types.ModuleType(name))

    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qtcore
    sys.modules["cerebro.core.fast_pipeline"] = fast_pipeline
    sys.modules["cerebro.core.models"] = models
    sys.modules["cerebro.ui.state_bus"] = state_bus


def _load_worker_module():
    _install_import_stubs()
    module_path = Path(__file__).with_name("fast_scan_worker.py")
    spec = importlib.util.spec_from_file_location("fast_scan_worker_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FastScanWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        _RecordingPipeline.instances.clear()

    def test_turbo_tier_uses_complete_duplicate_pipeline(self) -> None:
        module = _load_worker_module()
        worker = module.FastScanWorker({"root": "/tmp", "scanner_tier": "turbo"})

        worker.run()

        self.assertEqual(len(_RecordingPipeline.instances), 1)
        self.assertEqual(len(_RecordingPipeline.instances[0].run_calls), 1)
        self.assertEqual(len(worker.finished.emissions), 1)

        payload = worker.finished.emissions[0][0]
        self.assertEqual(payload["groups"], [{"hash": "same", "paths": ["/tmp/a.txt", "/tmp/b.txt"], "count": 2}])
        self.assertEqual(payload["group_count"], 1)
        self.assertEqual(payload["groups_found"], 1)
        self.assertEqual(payload["duplicate_count"], 2)
        self.assertEqual(payload["file_count"], 2)
        self.assertEqual(payload["scanner_tier"], "turbo")


if __name__ == "__main__":
    unittest.main()
