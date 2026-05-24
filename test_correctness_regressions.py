#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def install_fast_scan_worker_stubs() -> None:
    qtcore = types.ModuleType("PySide6.QtCore")

    class _Signal:
        def __init__(self, *args, **kwargs):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def emit(self, *args, **kwargs):
            for slot in self._slots:
                slot(*args, **kwargs)

    class _QThread:
        def __init__(self, *args, **kwargs):
            pass

    class _QObject:
        pass

    qtcore.Signal = _Signal
    qtcore.QThread = _QThread
    qtcore.QObject = _QObject

    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qtcore

    fast_pipeline = types.ModuleType("cerebro.core.fast_pipeline")
    fast_pipeline.FastPipeline = object

    core_models = types.ModuleType("cerebro.core.models")

    class _ScanProgress:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    core_models.ScanProgress = _ScanProgress

    state_bus = types.ModuleType("cerebro.ui.state_bus")

    class _StateBus:
        @staticmethod
        def allowed_extensions_for_media_type(media_type):
            return []

    state_bus.StateBus = _StateBus

    sys.modules.setdefault("PySide6", pyside)
    sys.modules.setdefault("PySide6.QtCore", qtcore)
    sys.modules.setdefault("cerebro", types.ModuleType("cerebro"))
    sys.modules.setdefault("cerebro.core", types.ModuleType("cerebro.core"))
    sys.modules["cerebro.core.fast_pipeline"] = fast_pipeline
    sys.modules["cerebro.core.models"] = core_models
    sys.modules.setdefault("cerebro.ui", types.ModuleType("cerebro.ui"))
    sys.modules["cerebro.ui.state_bus"] = state_bus


class OptimizedScanGroupTests(unittest.TestCase):
    def test_build_duplicate_groups_reconstructs_content_groups(self) -> None:
        install_fast_scan_worker_stubs()
        worker_module = load_module("fast_scan_worker_under_test", ROOT / "fast_scan_worker.py")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            duplicate_a = base / "a.bin"
            duplicate_b = base / "b.bin"
            same_size_different_content = base / "c.bin"
            unique_size = base / "d.bin"

            duplicate_a.write_bytes(b"abcdef")
            duplicate_b.write_bytes(b"abcdef")
            same_size_different_content.write_bytes(b"ghijkl")
            unique_size.write_bytes(b"abcdefghi")

            metadata = [
                SimpleNamespace(path=duplicate_a, size=duplicate_a.stat().st_size),
                SimpleNamespace(path=duplicate_b, size=duplicate_b.stat().st_size),
                SimpleNamespace(path=same_size_different_content, size=same_size_different_content.stat().st_size),
                SimpleNamespace(path=unique_size, size=unique_size.stat().st_size),
            ]

            groups = worker_module.build_duplicate_groups(metadata)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(groups[0]["size"], 6)
        self.assertEqual(groups[0]["recoverable_bytes"], 6)
        self.assertEqual(groups[0]["paths"], sorted([str(duplicate_a), str(duplicate_b)]))


class HashCacheTests(unittest.TestCase):
    def test_cache_read_validates_algorithm_and_quick_hash_bytes(self) -> None:
        hash_cache_module = load_module("hash_cache_under_test", ROOT / "hash_cache.py")
        HashCache = hash_cache_module.HashCache
        StatSignature = hash_cache_module.StatSignature

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "hash-cache.sqlite"
            file_path = Path(tmp) / "sample.txt"
            file_path.write_text("duplicate candidate", encoding="utf-8")
            sig = StatSignature.from_path(file_path)

            cache = HashCache(db_path)
            cache.open()
            try:
                cache.set_quick(file_path, sig, "md5-quick", algo="md5", quick_bytes=65536)
                cache.set_full(file_path, sig, "sha256-full", algo="sha256")

                self.assertEqual(cache.get_quick(file_path, sig), "md5-quick")
                self.assertEqual(cache.get_quick(file_path, sig, algo="md5", quick_bytes=65536), "md5-quick")
                self.assertIsNone(cache.get_quick(file_path, sig, algo="sha256", quick_bytes=65536))
                self.assertIsNone(cache.get_quick(file_path, sig, algo="md5", quick_bytes=1024))

                self.assertEqual(cache.get_full(file_path, sig), "sha256-full")
                self.assertEqual(cache.get_full(file_path, sig, algo="sha256"), "sha256-full")
                self.assertIsNone(cache.get_full(file_path, sig, algo="md5"))
            finally:
                cache.close()


if __name__ == "__main__":
    unittest.main()
