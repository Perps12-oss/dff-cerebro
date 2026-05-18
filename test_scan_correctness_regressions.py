#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).parent


class _Recorder:
    def __init__(self, *args, **kwargs):
        self.emissions = []

    def emit(self, *args):
        self.emissions.append(args)

    def connect(self, *args, **kwargs):
        return None


def _install_qt_stubs() -> None:
    qtcore = types.ModuleType("PySide6.QtCore")

    class QThread:
        def __init__(self, parent=None):
            self.parent = parent

    class QObject:
        pass

    qtcore.QThread = QThread
    qtcore.Signal = _Recorder
    qtcore.QObject = QObject

    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qtcore
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qtcore


def _install_cerebro_stubs() -> None:
    cerebro = sys.modules.setdefault("cerebro", types.ModuleType("cerebro"))
    core = sys.modules.setdefault("cerebro.core", types.ModuleType("cerebro.core"))
    ui = sys.modules.setdefault("cerebro.ui", types.ModuleType("cerebro.ui"))
    services = sys.modules.setdefault("cerebro.services", types.ModuleType("cerebro.services"))
    cerebro.core = core
    cerebro.ui = ui
    cerebro.services = services

    fast_pipeline = types.ModuleType("cerebro.core.fast_pipeline")

    class FakePipeline:
        instances = []

        def __init__(self, **kwargs):
            self.init_kwargs = kwargs
            self.run_kwargs = None
            FakePipeline.instances.append(self)

        def cancel(self):
            self.cancelled = True

        def run_fast_scan(self, root, **kwargs):
            self.root = root
            self.run_kwargs = kwargs
            return {
                "ok": True,
                "groups": [
                    {
                        "hash": "same-content",
                        "paths": [str(Path(root) / "a.txt"), str(Path(root) / "b.txt")],
                        "count": 2,
                    }
                ],
            }

    fast_pipeline.FastPipeline = FakePipeline
    sys.modules["cerebro.core.fast_pipeline"] = fast_pipeline
    core.fast_pipeline = fast_pipeline

    models = types.ModuleType("cerebro.core.models")

    @dataclass
    class ScanProgress:
        phase: str = ""
        message: str = ""
        percent: float = 0.0
        scanned_files: int = 0
        scanned_bytes: int = 0
        elapsed_seconds: float = 0.0
        estimated_total_files: int | None = None
        estimated_total_bytes: int | None = None
        current_path: str | None = None

    @dataclass
    class FileMetadata:
        path: Path
        size: int

        @classmethod
        def from_path(cls, path):
            path = Path(path)
            return cls(path=path, size=path.stat().st_size)

    models.ScanProgress = ScanProgress
    models.FileMetadata = FileMetadata
    sys.modules["cerebro.core.models"] = models
    core.models = models

    state_bus = types.ModuleType("cerebro.ui.state_bus")

    class StateBus:
        @staticmethod
        def allowed_extensions_for_media_type(media_type):
            return [".txt"] if media_type == "documents" else []

    state_bus.StateBus = StateBus
    sys.modules["cerebro.ui.state_bus"] = state_bus
    ui.state_bus = state_bus

    hash_cache = types.ModuleType("cerebro.services.hash_cache")

    class HashCache:
        def __init__(self, *args, **kwargs):
            pass

        def open(self):
            pass

        def close(self):
            pass

    class StatSignature:
        pass

    hash_cache.HashCache = HashCache
    hash_cache.StatSignature = StatSignature
    sys.modules["cerebro.services.hash_cache"] = hash_cache
    services.hash_cache = hash_cache


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScanCorrectnessRegressionTests(unittest.TestCase):
    def setUp(self):
        _install_qt_stubs()
        _install_cerebro_stubs()

    def test_turbo_worker_uses_duplicate_safe_pipeline_payload(self):
        module = _load_module("fast_scan_worker_under_test", ROOT / "fast_scan_worker.py")
        fake_pipeline = sys.modules["cerebro.core.fast_pipeline"].FastPipeline
        fake_pipeline.instances.clear()

        worker = module.FastScanWorker(
            {
                "root": "/tmp/cerebro-scan",
                "scanner_tier": "turbo",
                "min_size_bytes": 1,
                "include_hidden": True,
                "follow_symlinks": False,
                "allowed_extensions": ["txt"],
                "exclude_dirs": ["skip-me"],
            }
        )
        for signal_name in (
            "progress_updated",
            "phase_changed",
            "file_changed",
            "group_discovered",
            "warning_raised",
            "error_occurred",
            "finished",
            "failed",
            "cancelled",
        ):
            setattr(worker, signal_name, _Recorder())

        worker.run()

        self.assertEqual(worker.failed.emissions, [])
        self.assertEqual(len(worker.finished.emissions), 1)
        payload = worker.finished.emissions[0][0]
        self.assertEqual(payload["group_count"], 1)
        self.assertEqual(payload["groups_found"], 1)
        self.assertEqual(payload["duplicate_count"], 1)
        self.assertEqual(payload["scanner_tier"], "turbo")
        self.assertEqual(len(payload["groups"]), 1)

        self.assertEqual(len(fake_pipeline.instances), 1)
        self.assertEqual(fake_pipeline.instances[0].run_kwargs["allowed_extensions"], [".txt"])
        self.assertEqual(fake_pipeline.instances[0].run_kwargs["exclude_dirs"], ["skip-me"])

    def test_turbo_discovery_deduplicates_root_and_child_walks(self):
        module = _load_module("turbo_scanner_under_test", ROOT / "turbo_scanner.py")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child_dir = root / "child"
            child_dir.mkdir()
            nested_file = child_dir / "duplicate.txt"
            nested_file.write_text("same content")

            scanner = module.TurboScanner(
                module.TurboScanConfig(
                    use_cache=False,
                    use_multiprocessing=False,
                    min_size=1,
                    skip_hidden=False,
                    exclude_dirs=set(),
                )
            )
            discovered = scanner._discover_files_parallel([root])

        counts = Counter(str(path) for path, _size, _mtime in discovered)
        self.assertEqual(counts[str(nested_file)], 1)


if __name__ == "__main__":
    unittest.main()
