#!/usr/bin/env python3
"""Focused regression tests for deletion safety invariants."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load_deletion_module():
    module_path = Path(__file__).with_name("deletion.py")
    spec = importlib.util.spec_from_file_location("deletion", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


deletion = _load_deletion_module()


class DeletionSafetyTests(unittest.TestCase):
    def _plan(self, *, scan_id: str, keeper: Path, delete_path: Path):
        operation = SimpleNamespace(path=delete_path, size=delete_path.stat().st_size, kept_path=keeper)
        return SimpleNamespace(scan_id=scan_id, mode="permanent", operations=[operation])

    def test_execute_plan_refuses_delete_when_keeper_disappears(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            keeper = root / "keeper.txt"
            duplicate = root / "duplicate.txt"
            keeper.write_text("same contents", encoding="utf-8")
            duplicate.write_text("same contents", encoding="utf-8")

            plan = self._plan(scan_id="keeper-race", keeper=keeper, delete_path=duplicate)
            keeper.unlink()

            engine = deletion.DeletionEngine()
            result = engine.execute_plan(
                plan,
                request=deletion.DeletionRequest(policy=deletion.DeletionPolicy.PERMANENT),
            )

            self.assertEqual([], result.deleted)
            self.assertEqual(1, len(result.failed))
            self.assertIn("Keeper no longer exists", result.failed[0][1])
            self.assertTrue(duplicate.exists())

    def test_execute_plan_deletes_candidate_when_keeper_still_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            keeper = root / "keeper.txt"
            duplicate = root / "duplicate.txt"
            keeper.write_text("same contents", encoding="utf-8")
            duplicate.write_text("same contents", encoding="utf-8")

            plan = self._plan(scan_id="valid-delete", keeper=keeper, delete_path=duplicate)

            engine = deletion.DeletionEngine()
            result = engine.execute_plan(
                plan,
                request=deletion.DeletionRequest(policy=deletion.DeletionPolicy.PERMANENT),
            )

            self.assertEqual([duplicate], result.deleted)
            self.assertEqual([], result.failed)
            self.assertTrue(keeper.exists())
            self.assertFalse(duplicate.exists())


if __name__ == "__main__":
    unittest.main()
