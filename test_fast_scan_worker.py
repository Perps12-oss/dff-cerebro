#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path


class _Signal:
    def __init__(self, *args, **kwargs):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _QThread:
    def __init__(self, parent=None):
        self.parent = parent

    def start(self):
        self.run()


class _QObject:
    pass


@dataclass
class _ScanProgress:
    phase: str = ""
    message: str = ""
    percent: float = 0.0
    scanned_files: int = 0
    scanned_bytes: int = 0
    elapsed_seconds: float = 0.0
    estimated_total_files: int | None = None
    estimated_total_bytes: int | None = None
    current_path: str | None = None


class _StateBus:
    @staticmethod
    def allowed_extensions_for_media_type(media_type: str):
        return None


class _PlaceholderFastPipeline:
    def __init__(self, *args, **kwargs):
        pass


def _install_module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def _install_import_stubs() -> None:
    pyside = _install_module("PySide6")
    qtcore = _install_module("PySide6.QtCore")
    qtcore.QThread = _QThread
    qtcore.Signal = _Signal
    qtcore.QObject = _QObject
    pyside.QtCore = qtcore

    for package in [
        "cerebro",
        "cerebro.core",
        "cerebro.ui",
    ]:
        _install_module(package)

    fast_pipeline = _install_module("cerebro.core.fast_pipeline")
    fast_pipeline.FastPipeline = _PlaceholderFastPipeline

    models = _install_module("cerebro.core.models")
    models.ScanProgress = _ScanProgress

    state_bus = _install_module("cerebro.ui.state_bus")
    state_bus.StateBus = _StateBus


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
    @classmethod
    def setUpClass(cls):
        cls.module = _load_worker_module()

    def test_normalizes_pipeline_groups_and_counts(self):
        payload = self.module.FastScanWorker._normalize_result_payload(
            {
                "groups": [
                    {"hash": "h1", "paths": ["/tmp/a", "/tmp/b"]},
                    {"hash": "h2", "paths": ["/tmp/c", "/tmp/d", "/tmp/e"]},
                ],
                "stats": {"files_scanned": 12, "time_seconds": 1.25},
            },
            root="/tmp",
            scan_name="Scan of /tmp",
            scanner_tier="turbo",
        )

        self.assertEqual(payload["group_count"], 2)
        self.assertEqual(payload["groups_found"], 2)
        self.assertEqual(payload["duplicate_count"], 3)
        self.assertEqual(payload["file_count"], 12)
        self.assertEqual(payload["scan_duration"], 1.25)
        self.assertEqual(payload["scanner_tier"], "turbo")

    def test_normalizes_dict_group_mapping(self):
        payload = self.module.FastScanWorker._normalize_result_payload(
            {"groups": {"abc": ["/tmp/a", "/tmp/b"]}},
            root="/tmp",
            scan_name="Scan of /tmp",
            scanner_tier="turbo",
        )

        self.assertEqual(payload["groups"], [{"hash": "abc", "paths": ["/tmp/a", "/tmp/b"]}])
        self.assertEqual(payload["group_count"], 1)
        self.assertEqual(payload["duplicate_count"], 1)

    def test_turbo_worker_uses_pipeline_group_contract(self):
        calls = []

        class FakeFastPipeline:
            def __init__(self, **kwargs):
                calls.append(("init", kwargs))

            def cancel(self):
                calls.append(("cancel", None))

            def run_fast_scan(self, root, **kwargs):
                calls.append(("run_fast_scan", root, kwargs))
                return {
                    "groups": [{"hash": "same", "paths": ["/tmp/a.txt", "/tmp/b.txt"]}],
                    "stats": {"files_scanned": 2, "time_seconds": 0.5},
                }

        self.module.FastPipeline = FakeFastPipeline

        worker = self.module.FastScanWorker({"root": "/tmp", "scanner_tier": "turbo"})
        finished_payloads = []
        worker.finished.connect(finished_payloads.append)

        worker.run()

        self.assertEqual(calls[0][0], "init")
        self.assertEqual(calls[1][0], "run_fast_scan")
        self.assertEqual(calls[1][1], "/tmp")
        self.assertEqual(finished_payloads[-1]["group_count"], 1)
        self.assertEqual(finished_payloads[-1]["duplicate_count"], 1)
        self.assertEqual(finished_payloads[-1]["groups"][0]["paths"], ["/tmp/a.txt", "/tmp/b.txt"])


if __name__ == "__main__":
    unittest.main()
