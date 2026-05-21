#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent


def load_fast_pipeline_module():
    """Load fast_pipeline.py with the minimal package stubs it imports."""
    cerebro = sys.modules.setdefault("cerebro", types.ModuleType("cerebro"))
    services = sys.modules.setdefault("cerebro.services", types.ModuleType("cerebro.services"))
    setattr(cerebro, "services", services)

    hash_cache = types.ModuleType("cerebro.services.hash_cache")

    @dataclass(frozen=True)
    class StatSignature:
        size: int
        mtime_ns: int
        dev: int
        inode: int

    class HashCache:
        def __init__(self, db_path):
            self.db_path = db_path

        def open(self):
            return None

        def close(self):
            return None

        def get_quick(self, path, sig):
            return None

        def set_quick(self, path, sig, quick_hash, algo="md5"):
            return None

    hash_cache.HashCache = HashCache
    hash_cache.StatSignature = StatSignature
    sys.modules["cerebro.services.hash_cache"] = hash_cache

    spec = importlib.util.spec_from_file_location("fast_pipeline_under_test", ROOT_DIR / "fast_pipeline.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FastPipelineCorrectnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fast_pipeline = load_fast_pipeline_module()

    def test_large_files_with_same_sampled_chunks_are_not_grouped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            size = 5 * 1024 * 1024
            first = bytearray(b"A" * size)
            second = bytearray(first)
            second[(1 * 1024 * 1024) + 123] = ord("B")

            (root / "first.bin").write_bytes(first)
            (root / "second.bin").write_bytes(second)

            pipeline = self.fast_pipeline.FastPipeline(max_workers=1)
            result = pipeline.run_fast_scan(root, min_size=1)

            self.assertTrue(result["ok"])
            self.assertEqual([], result["groups"])

    def test_exact_large_duplicates_are_grouped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = b"duplicate-data" * 400_000

            (root / "a.bin").write_bytes(content)
            (root / "b.bin").write_bytes(content)

            pipeline = self.fast_pipeline.FastPipeline(max_workers=1)
            result = pipeline.run_fast_scan(root, min_size=1)

            self.assertTrue(result["ok"])
            self.assertEqual(1, len(result["groups"]))
            self.assertEqual(2, result["groups"][0]["count"])


if __name__ == "__main__":
    unittest.main()
