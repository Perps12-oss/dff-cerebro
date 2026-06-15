#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _install_package_stubs() -> None:
    for name in ("cerebro", "cerebro.core", "cerebro.services", "cerebro.ui", "cerebro.workers"):
        sys.modules.setdefault(name, types.ModuleType(name))


def _load_fast_pipeline():
    _install_package_stubs()
    _load_module("cerebro.services.hash_cache", ROOT / "hash_cache.py")
    return _load_module("cerebro.core.fast_pipeline", ROOT / "fast_pipeline.py")


class _Signal:
    def __init__(self, *args, **kwargs):
        self.emissions = []

    def emit(self, *args):
        self.emissions.append(args)

    def connect(self, callback):
        return None


class _QThread:
    def __init__(self, parent=None):
        self.parent = parent


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
        return []


def _load_fast_scan_worker():
    fast_pipeline = _load_fast_pipeline()
    core_models = types.ModuleType("cerebro.core.models")
    core_models.ScanProgress = _ScanProgress
    sys.modules["cerebro.core.models"] = core_models

    state_bus = types.ModuleType("cerebro.ui.state_bus")
    state_bus.StateBus = _StateBus
    sys.modules["cerebro.ui.state_bus"] = state_bus

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QThread = _QThread
    qtcore.Signal = _Signal
    qtcore.QObject = _QObject
    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qtcore
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qtcore

    sys.modules["cerebro.core.fast_pipeline"] = fast_pipeline
    return _load_module("cerebro.workers.fast_scan_worker", ROOT / "fast_scan_worker.py")


class ScanRegressionTests(unittest.TestCase):
    def test_fast_pipeline_full_hash_verifies_sampled_hash_collisions(self):
        fast_pipeline = _load_fast_pipeline()
        pipeline = fast_pipeline.FastPipeline(max_workers=2)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            size = 6 * 1024 * 1024

            sampled_collision_a = bytearray(b"\0" * size)
            sampled_collision_b = bytearray(sampled_collision_a)
            sampled_collision_b[1_500_000] = 1
            (root / "collision-a.bin").write_bytes(sampled_collision_a)
            (root / "collision-b.bin").write_bytes(sampled_collision_b)

            identical = b"z" * size
            (root / "dupe-a.bin").write_bytes(identical)
            (root / "dupe-b.bin").write_bytes(identical)

            result = pipeline.run_fast_scan(root, min_size=1)

        groups = result["groups"]
        grouped_names = {frozenset(Path(p).name for p in group["paths"]) for group in groups}
        self.assertEqual({frozenset({"dupe-a.bin", "dupe-b.bin"})}, grouped_names)

    def test_default_turbo_worker_uses_duplicate_pipeline_payload(self):
        worker_module = _load_fast_scan_worker()

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "one.txt").write_bytes(b"same content" * 200)
            (root / "two.txt").write_bytes(b"same content" * 200)

            worker = worker_module.FastScanWorker({
                "root": str(root),
                "scanner_tier": "turbo",
                "min_size_bytes": 1,
            })
            worker.run()

        self.assertFalse(worker.failed.emissions)
        self.assertTrue(worker.finished.emissions)
        payload = worker.finished.emissions[-1][0]
        self.assertIsInstance(payload["groups"], list)
        self.assertEqual(1, payload["group_count"])
        self.assertEqual(1, payload["groups_found"])
        self.assertEqual(1, payload["duplicate_count"])


if __name__ == "__main__":
    unittest.main()
