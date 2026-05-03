import importlib.util
from pathlib import Path
from types import SimpleNamespace


_MODULE_PATH = Path(__file__).resolve().parent / "pages" / "review_plan.py"
_SPEC = importlib.util.spec_from_file_location("review_plan", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_review_plan = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_review_plan)
build_deletion_plan_groups = _review_plan.build_deletion_plan_groups


def test_build_deletion_plan_groups_emits_keep_delete_contract(tmp_path: Path) -> None:
    keep_path = tmp_path / "keeper.txt"
    delete_path = tmp_path / "duplicate.txt"
    other_path = tmp_path / "other.txt"
    keep_path.write_text("keep", encoding="utf-8")
    delete_path.write_text("delete-me", encoding="utf-8")
    other_path.write_text("other", encoding="utf-8")

    group = SimpleNamespace(
        paths=[str(keep_path), str(delete_path), str(other_path)],
        group_id=7,
        hint="same hash",
    )
    keep_states = {
        7: {
            str(keep_path): True,
            str(delete_path): False,
            str(other_path): True,
        }
    }

    plan_groups, total_size = build_deletion_plan_groups([group], keep_states)

    assert plan_groups == [
        {
            "group_index": 7,
            "keep": str(keep_path),
            "delete": [str(delete_path)],
            "hint": "same hash",
            "recoverable_bytes": delete_path.stat().st_size,
        }
    ]
    assert total_size == delete_path.stat().st_size


def test_build_deletion_plan_groups_skips_groups_without_survivor() -> None:
    group = SimpleNamespace(paths=["/tmp/a", "/tmp/b"], group_id=1, hint="")
    keep_states = {1: {"/tmp/a": False, "/tmp/b": False}}

    plan_groups, total_size = build_deletion_plan_groups([group], keep_states)

    assert plan_groups == []
    assert total_size == 0
