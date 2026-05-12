import tempfile
import unittest
from pathlib import Path
from unittest import mock

import deletion
from deletion import DeletionPolicy, DeletionRequest, TrashDeletionAdapter


class _FixedDatetime:
    @staticmethod
    def now():
        return _FixedDatetime()

    def strftime(self, fmt):
        return "20260512_110145"

    def timestamp(self):
        return 0.0


class TrashDeletionAdapterTests(unittest.TestCase):
    def test_fallback_trash_keeps_same_named_files_from_same_second(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_dir = root / "first"
            second_dir = root / "second"
            first_dir.mkdir()
            second_dir.mkdir()
            first = first_dir / "duplicate.txt"
            second = second_dir / "duplicate.txt"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")

            adapter = TrashDeletionAdapter()
            adapter._send2trash_available = False
            request = DeletionRequest(policy=DeletionPolicy.TRASH)

            with (
                mock.patch.object(deletion.Path, "home", return_value=root),
                mock.patch.object(deletion, "datetime", _FixedDatetime),
            ):
                first_result = adapter.delete(first, request)
                second_result = adapter.delete(second, request)

            self.assertTrue(first_result.success, first_result.error)
            self.assertTrue(second_result.success, second_result.error)
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())

            trashed_files = sorted((root / ".cerebro" / "trash").glob("*_duplicate.txt"))
            self.assertEqual(2, len(trashed_files))
            self.assertEqual(
                ["first", "second"],
                sorted(path.read_text(encoding="utf-8") for path in trashed_files),
            )


if __name__ == "__main__":
    unittest.main()
