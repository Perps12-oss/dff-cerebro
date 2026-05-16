from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple


def _group_value(group: Any, name: str, default: Any = None) -> Any:
    if isinstance(group, Mapping):
        return group.get(name, default)
    return getattr(group, name, default)


def build_cleanup_groups(
    groups: Sequence[Any],
    keep_states: Mapping[int, Mapping[str, bool]],
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Convert ReviewPage selection state into the strict DeletionPlan group shape.

    MainWindow deliberately refuses ambiguous legacy payloads, so every cleanup
    group must name one keeper and the exact delete candidates.
    """
    delete_groups: List[Dict[str, Any]] = []
    total_delete_size = 0

    for idx, group in enumerate(groups):
        group_id = int(_group_value(group, "group_id", idx) or 0)
        paths = [str(p) for p in (_group_value(group, "paths", []) or [])]
        keep_map = keep_states.get(group_id, {})

        delete_paths = [p for p in paths if not bool(keep_map.get(p, True))]
        if not delete_paths:
            continue

        keep_paths = [p for p in paths if bool(keep_map.get(p, True))]
        if not keep_paths:
            raise ValueError(f"Group {group_id} has no keeper; refusing cleanup.")

        group_size = 0
        for path in delete_paths:
            try:
                p = Path(path)
                if p.exists():
                    group_size += p.stat().st_size
            except OSError:
                continue

        total_delete_size += group_size
        delete_groups.append({
            "group_index": group_id,
            "keep": keep_paths[0],
            "delete": delete_paths,
            # Keep legacy metadata for dialogs/history consumers that still read it.
            "paths": delete_paths,
            "hint": str(_group_value(group, "hint", "") or ""),
            "recoverable_bytes": group_size,
        })

    return delete_groups, total_delete_size
