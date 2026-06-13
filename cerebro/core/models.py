"""Core compatibility models used by scanners, workers, and UI telemetry."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class PipelineMode(str, Enum):
    STANDARD = "standard"
    FAST = "fast"
    THOROUGH = "thorough"


class DeletionPolicy(str, Enum):
    MOVE_TO_TRASH = "move_to_trash"
    DELETE_PERMANENTLY = "delete_permanently"
    DRY_RUN = "dry_run"


@dataclass(slots=True)
class StartScanConfig:
    root: str = ""
    fast_mode: bool = False
    mode: str = PipelineMode.STANDARD.value
    min_size_bytes: int = 1024
    include_hidden: bool = False
    follow_symlinks: bool = False
    media_type: str = "all"
    engine: str = "simple"


@dataclass(slots=True)
class PipelineRequest:
    roots: List[Path] = field(default_factory=list)
    mode: PipelineMode = PipelineMode.STANDARD
    validation_mode: bool = False
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FileMetadata:
    path: Path
    size: int = 0
    mtime: float = 0.0
    extension: str = ""
    is_hidden: bool = False

    @classmethod
    def from_path(cls, path: Path | str) -> Optional["FileMetadata"]:
        p = Path(path)
        try:
            st = p.stat()
        except OSError:
            return None
        return cls(
            path=p,
            size=int(st.st_size or 0),
            mtime=float(st.st_mtime or 0.0),
            extension=p.suffix.lower(),
            is_hidden=p.name.startswith("."),
        )


@dataclass(slots=True)
class FileItem:
    path: Path
    metadata: Optional[FileMetadata] = None


@dataclass(slots=True)
class DuplicateItem:
    file: FileItem
    path: Path
    size_bytes: int = 0
    hash: str = ""


@dataclass(slots=True)
class DuplicateGroup:
    items: List[DuplicateItem] = field(default_factory=list)
    group_id: str = ""


@dataclass(slots=True)
class ScanProgress:
    phase: str = ""
    message: str = ""
    percent: float = 0.0
    scanned_files: int = 0
    scanned_bytes: int = 0
    elapsed_seconds: float = 0.0
    estimated_total_files: Optional[int] = None
    estimated_total_bytes: Optional[int] = None
    current_path: Optional[str] = None


__all__ = [
    "DeletionPolicy",
    "DuplicateGroup",
    "DuplicateItem",
    "FileItem",
    "FileMetadata",
    "PipelineMode",
    "PipelineRequest",
    "ScanProgress",
    "StartScanConfig",
]
