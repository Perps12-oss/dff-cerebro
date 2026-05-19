#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).parent


def _load_fast_pipeline_module():
    """Load fast_pipeline.py without requiring the full installed package layout."""
    cerebro = sys.modules.setdefault("cerebro", types.ModuleType("cerebro"))
    services = sys.modules.setdefault("cerebro.services", types.ModuleType("cerebro.services"))
    setattr(cerebro, "services", services)

    hash_cache = types.ModuleType("cerebro.services.hash_cache")

    @dataclass(frozen=True)
    class StatSignature:
        size: int
        mtime_ns: int
        dev: int = 0
        inode: int = 0

    class HashCache:
        def __init__(self, db_path):
            self.db_path = Path(db_path)

        def open(self):
            return None

        def close(self):
            return None

        def get_full(self, path, sig):
            return None

        def set_full(self, path, sig, full_hash, *, algo="md5"):
            return None

    hash_cache.HashCache = HashCache
    hash_cache.StatSignature = StatSignature
    sys.modules["cerebro.services.hash_cache"] = hash_cache

    spec = importlib.util.spec_from_file_location("critical_fast_pipeline", ROOT / "fast_pipeline.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class CriticalRegressionTests(unittest.TestCase):
    def test_fast_pipeline_uses_full_hashes_for_duplicate_groups(self):
        module = _load_fast_pipeline_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "left.bin"
            right = root / "right.bin"
            clone = root / "clone.bin"

            data = bytearray(b"A" * (4 * 1024 * 1024))
            left.write_bytes(data)
            clone.write_bytes(data)

            near_match = bytearray(data)
            near_match[1280 * 1024] = ord("B")
            right.write_bytes(near_match)

            pipeline = module.FastPipeline(max_workers=2)
            result = pipeline.run_fast_scan(root, min_size=1)

            groups = result["groups"]
            grouped_paths = [set(group["paths"]) for group in groups]

            self.assertIn({str(left), str(clone)}, grouped_paths)
            self.assertNotIn({str(left), str(right), str(clone)}, grouped_paths)
            for group in groups:
                self.assertNotIn(str(right), group["paths"])

    def test_history_schema_migration_preserves_existing_entries(self):
        from pages.models import HISTORY_SCHEMA_VERSION
        from pages.store import HistoryStore

        with tempfile.TemporaryDirectory() as tmp:
            store = HistoryStore(base_dir=Path(tmp))
            old_entry = {
                "scan_id": "old-scan",
                "name": "Old scan",
                "root_path": str(Path(tmp)),
                "status": "completed",
            }
            store.index_path.write_text(
                json.dumps({"schema_version": HISTORY_SCHEMA_VERSION - 1, "entries": [old_entry]}),
                encoding="utf-8",
            )

            migrated = store._read_index_unlocked()
            self.assertEqual(migrated["schema_version"], HISTORY_SCHEMA_VERSION)
            self.assertEqual(migrated["entries"], [old_entry])

            new_entry = store.begin_scan(str(Path(tmp)), {}, name="New scan")
            written = json.loads(store.index_path.read_text(encoding="utf-8"))
            scan_ids = {entry["scan_id"] for entry in written["entries"]}
            self.assertIn("old-scan", scan_ids)
            self.assertIn(new_entry.scan_id, scan_ids)


if __name__ == "__main__":
    unittest.main()
