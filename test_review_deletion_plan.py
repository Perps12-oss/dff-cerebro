from __future__ import annotations

import importlib.util
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "pages" / "review_deletion_plan.py"
SPEC = importlib.util.spec_from_file_location("review_deletion_plan_under_test", MODULE_PATH)
review_deletion_plan = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(review_deletion_plan)


@dataclass(frozen=True)
class Group:
    paths: list[str]
    hint: str = ""
    group_id: int = 0


class ReviewDeletionPlanTests(unittest.TestCase):
    def test_builds_strict_keep_delete_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            keep = root / "keep.txt"
            delete = root / "delete.txt"
            keep.write_text("survivor", encoding="utf-8")
            delete.write_text("duplicate", encoding="utf-8")

            groups, total_size = review_deletion_plan.build_cleanup_groups(
                [Group(paths=[str(keep), str(delete)], hint="same hash", group_id=7)],
                {7: {str(keep): True, str(delete): False}},
            )

        self.assertEqual(total_size, len("duplicate"))
        self.assertEqual(groups, [{
            "group_index": 7,
            "keep": str(keep),
            "delete": [str(delete)],
            "paths": [str(delete)],
            "hint": "same hash",
            "recoverable_bytes": len("duplicate"),
        }])

    def test_refuses_group_without_keeper(self) -> None:
        group = Group(paths=["/tmp/a", "/tmp/b"], group_id=3)

        with self.assertRaisesRegex(ValueError, "no keeper"):
            review_deletion_plan.build_cleanup_groups(
                [group],
                {3: {"/tmp/a": False, "/tmp/b": False}},
            )


if __name__ == "__main__":
    unittest.main()
