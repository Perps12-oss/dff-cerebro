import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import deletion
from deletion import DeletionPolicy, DeletionRequest, TrashDeletionAdapter


class _FixedDateTime:
    @classmethod
    def now(cls):
        return cls()

    def strftime(self, fmt):
        return "20260513_110000"


class TrashDeletionAdapterTests(unittest.TestCase):
    def test_fallback_trash_preserves_same_basename_deletions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            first_dir = root / "first"
            second_dir = root / "second"
            home.mkdir()
            first_dir.mkdir()
            second_dir.mkdir()

            first_file = first_dir / "duplicate.txt"
            second_file = second_dir / "duplicate.txt"
            first_file.write_text("first", encoding="utf-8")
            second_file.write_text("second", encoding="utf-8")

            adapter = TrashDeletionAdapter()
            adapter._send2trash_available = False
            request = DeletionRequest(policy=DeletionPolicy.TRASH)

            with patch.dict(os.environ, {"HOME": str(home)}), patch.object(deletion, "datetime", _FixedDateTime):
                first_result = adapter.delete(first_file, request)
                second_result = adapter.delete(second_file, request)

            self.assertTrue(first_result.success)
            self.assertTrue(second_result.success)
            self.assertFalse(first_file.exists())
            self.assertFalse(second_file.exists())

            trashed_files = sorted((home / ".cerebro" / "trash").glob("*_duplicate.txt"))
            self.assertEqual(len(trashed_files), 2)
            self.assertEqual(
                {p.read_text(encoding="utf-8") for p in trashed_files},
                {"first", "second"},
            )


if __name__ == "__main__":
    unittest.main()
