from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Mapping, Tuple


def build_deletion_plan_groups(
    groups: Iterable[Any],
    keep_states: Mapping[int, Mapping[str, bool]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Build authoritative keep/delete groups from ReviewPage selection state."""
    plan_groups: List[Dict[str, Any]] = []
    total_delete_size = 0

    for fallback_index, group in enumerate(groups):
        paths = [str(p) for p in getattr(group, "paths", [])]
        group_id = int(getattr(group, "group_id", fallback_index) or 0)
        keep_map = dict(keep_states.get(group_id, {}) or {})

        delete_paths = [p for p in paths if not keep_map.get(p, True)]
        if not delete_paths:
            continue

        keep_paths = [p for p in paths if keep_map.get(p, True)]
        if not keep_paths:
            # The UI normally prevents this; skipping is safer than emitting a
            # plan with no survivor for the pipeline to validate.
            continue

        group_size = sum(os.path.getsize(p) for p in delete_paths if os.path.exists(p))
        total_delete_size += group_size

        plan_groups.append(
            {
                "group_index": group_id,
                "keep": keep_paths[0],
                "delete": delete_paths,
                "hint": str(getattr(group, "hint", "") or ""),
                "recoverable_bytes": group_size,
            }
        )

    return plan_groups, total_delete_size
