# cerebro/workers/fast_scan_worker.py
from __future__ import annotations

import sys
import time
import traceback
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QThread, Signal, QObject

from cerebro.core.fast_pipeline import FastPipeline
from cerebro.core.models import ScanProgress
from cerebro.ui.state_bus import StateBus


@dataclass(frozen=True, slots=True)
class FastScanConfig:
    root: str
    min_size_bytes: int = 1024
    include_hidden: bool = False
    follow_symlinks: bool = False
    allowed_extensions: Optional[List[str]] = None
    exclude_dirs: Optional[List[str]] = None
    max_workers: int = 0  # 0 = auto
    cache_path: Optional[str] = None
    scan_name: Optional[str] = None
    media_type: str = "all"
    engine: str = "simple"
    scanner_tier: str = "turbo"  # NEW: turbo/ultra/quantum

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FastScanConfig":
        if "root" not in d:
            raise ValueError("FastScanConfig requires 'root'")
        allowed = d.get("allowed_extensions") or d.get("file_types")
        media_type = str(d.get("media_type", "all")).lower()
        if not allowed and media_type and media_type != "all":
            allowed = StateBus.allowed_extensions_for_media_type(media_type)
        if allowed is not None:
            allowed = [e if e.startswith(".") else f".{e}" for e in (allowed or [])]
        return cls(
            root=str(d["root"]),
            min_size_bytes=int(d.get("min_size_bytes", 1024)),
            include_hidden=bool(d.get("include_hidden", False)),
            follow_symlinks=bool(d.get("follow_symlinks", False)),
            allowed_extensions=allowed or None,
            exclude_dirs=list(d.get("exclude_dirs") or []) or None,
            max_workers=int(d.get("max_workers", 0)),
            cache_path=d.get("cache_path"),
            scan_name=d.get("scan_name"),
            media_type=media_type,
            engine=str(d.get("engine", "simple")).lower(),
            scanner_tier=str(d.get("scanner_tier", "turbo")).lower(),  # NEW
        )


class FastScanWorker(QThread):
    """
    PySide6-only.
    Emits semantic scan signals consumed by LiveScanController.

    Signals:
      - progress_updated(ScanProgress)
      - phase_changed(str)
      - file_changed(str)
      - group_discovered(int)      # delta (typically +1)
      - warning_raised(str, str)   # path, reason
      - error_occurred(str)
      - finished(dict)
      - failed(str)
      - cancelled()
    """
    progress_updated = Signal(object)
    phase_changed = Signal(str)
    file_changed = Signal(str)
    group_discovered = Signal(int)
    warning_raised = Signal(str, str)
    error_occurred = Signal(str)

    finished = Signal(dict)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, config: Dict[str, Any], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._cfg = FastScanConfig.from_dict(config)
        self._pipeline: Optional[FastPipeline] = None
        self._cancelled = False

        self._start_ts = 0.0
        self._last_groups = 0

    def cancel(self) -> None:
        self._cancelled = True
        if self._pipeline is not None:
            try:
                self._pipeline.cancel()
            except Exception:
                pass

    def run(self) -> None:
        self._start_ts = time.perf_counter()
        self._last_groups = 0

        try:
            # Turbo is the default production path. It must return duplicate groups,
            # not just discovered files, because ReviewPage consumes groups directly.
            if self._cfg.scanner_tier == "turbo":
                self.phase_changed.emit("TurboScanner: Scanning for exact duplicates...")
                self._run_fast_pipeline_scan(scanner_tier="turbo", scanner_name="TurboScanner")
                return

            # Experimental tiers keep their specialized discovery path.
            if self._cfg.scanner_tier in ("ultra", "quantum"):
                self._run_optimized_scan()
                return

            # Fall back to legacy FastPipeline
            self._run_fast_pipeline_scan()

        except Exception as e:
            msg = f"{e}"
            tb = traceback.format_exc()
            self.error_occurred.emit(msg)
            self.failed.emit(tb)

    def _run_fast_pipeline_scan(
        self,
        *,
        scanner_tier: Optional[str] = None,
        scanner_name: Optional[str] = None,
    ) -> None:
        root = str(self._cfg.root)

        self._pipeline = FastPipeline(
            max_workers=self._cfg.max_workers,
            cache_path=self._cfg.cache_path,
            engine=self._cfg.engine,
        )

        try:
            def progress_cb(percent: int, message: str, stats: Dict[str, Any]) -> None:
                if self._cancelled:
                    return

                phase = str(stats.get("phase") or "")
                if phase:
                    self.phase_changed.emit(phase)

                current_path = str(stats.get("current_path") or stats.get("current_file") or "")
                if current_path:
                    self.file_changed.emit(current_path)

                groups_found = stats.get("groups_found")
                if groups_found is not None:
                    try:
                        g = int(groups_found)
                        delta = g - self._last_groups
                        if delta > 0:
                            self.group_discovered.emit(delta)
                        self._last_groups = g
                    except Exception:
                        pass

                warn = stats.get("warning")
                if warn:
                    self.warning_raised.emit(current_path, str(warn))

                elapsed = max(0.0, time.perf_counter() - self._start_ts)
                prog = ScanProgress(
                    phase=phase,
                    message=str(message or ""),
                    percent=float(percent),
                    scanned_files=int(stats.get("scanned_files", stats.get("files_scanned", 0)) or 0),
                    scanned_bytes=int(stats.get("scanned_bytes", stats.get("bytes_scanned", 0)) or 0),
                    elapsed_seconds=float(stats.get("elapsed_seconds", stats.get("elapsed", elapsed)) or elapsed),
                    estimated_total_files=stats.get("estimated_total_files", stats.get("total_files")),
                    estimated_total_bytes=stats.get("estimated_total_bytes", stats.get("total_bytes")),
                    current_path=current_path or None,
                )
                self.progress_updated.emit(prog)

            result = self._pipeline.run_fast_scan(
                root,
                min_size=self._cfg.min_size_bytes,
                include_hidden=self._cfg.include_hidden,
                follow_symlinks=self._cfg.follow_symlinks,
                allowed_extensions=self._cfg.allowed_extensions,
                exclude_dirs=self._cfg.exclude_dirs,
                progress_cb=progress_cb,
            )

            if self._cancelled or bool(result.get("cancelled", False)):
                self.cancelled.emit()
                return

            # Normalize payload fields for UI
            payload = dict(result or {})
            groups = payload.get("groups") or []
            stats = dict(payload.get("stats") or {})
            group_count = len(groups) if isinstance(groups, list) else int(payload.get("group_count", 0) or 0)
            duplicate_count = 0
            if isinstance(groups, list):
                duplicate_count = sum(len(g.get("paths") or []) for g in groups if isinstance(g, dict))

            payload.setdefault("scan_root", root)
            payload.setdefault("scan_name", self._cfg.scan_name or f"Scan of {root}")
            payload.setdefault("groups", groups)
            payload.setdefault("group_count", group_count)
            payload.setdefault("groups_found", group_count)
            payload.setdefault("duplicate_count", duplicate_count)
            payload.setdefault("file_count", int(payload.get("file_count", stats.get("files_scanned", 0)) or 0))
            payload.setdefault("total_size", int(payload.get("total_size", stats.get("total_size", 0)) or 0))
            payload.setdefault("scan_duration", float(payload.get("scan_duration", stats.get("time_seconds", 0.0)) or 0.0))
            if scanner_tier:
                payload.setdefault("scanner_tier", scanner_tier)
            if scanner_name:
                payload.setdefault("scanner_name", scanner_name)

            self.finished.emit(payload)

        except Exception as e:
            msg = f"{e}"
            tb = traceback.format_exc()
            self.error_occurred.emit(msg)
            self.failed.emit(tb)
    
    def _run_optimized_scan(self) -> None:
        """Run scan using optimized scanner tiers (Turbo/Ultra/Quantum)."""
        try:
            root = Path(self._cfg.root)
            tier = self._cfg.scanner_tier
            
            # Phase: Setup
            self.phase_changed.emit("Initializing scanner...")
            
            # Initialize the appropriate scanner
            scanner = None
            scanner_name = "Unknown"
            
            if tier == "turbo":
                try:
                    from cerebro.core.scanner_adapter import create_optimized_scanner
                    scanner = create_optimized_scanner()
                    scanner_name = "TurboScanner"
                    self.phase_changed.emit("TurboScanner initialized (12x faster)")
                except ImportError as e:
                    self.failed.emit(f"TurboScanner not available: {e}")
                    return
            
            elif tier == "ultra":
                try:
                    from cerebro.core.scanners.ultra_scanner import UltraScanner, UltraScanConfig
                    
                    config = UltraScanConfig(
                        min_size=self._cfg.min_size_bytes,
                        skip_hidden=not self._cfg.include_hidden,
                        exclude_dirs=set(self._cfg.exclude_dirs or []),
                        use_bloom_filter=True,
                        use_simd_hash=True,
                        use_everything_sdk=(sys.platform == 'win32'),
                        dir_workers=min(64, self._cfg.max_workers * 4) if self._cfg.max_workers else 64,
                        hash_workers=min(128, self._cfg.max_workers * 8) if self._cfg.max_workers else 128,
                    )
                    
                    scanner = UltraScanner(config)
                    scanner_name = "UltraScanner"
                    self.phase_changed.emit("UltraScanner initialized (60x faster)")
                except ImportError as e:
                    self.failed.emit(f"UltraScanner not available: {e}\nInstall: pip install xxhash mmh3 numpy")
                    return
            
            elif tier == "quantum":
                try:
                    from cerebro.core.scanners.quantum_scanner import QuantumScanner, QuantumScanConfig
                    
                    config = QuantumScanConfig(
                        use_gpu=True,
                        gpu_device="cuda",
                        use_neural_predictor=True,
                        use_async_io=True,
                    )
                    
                    scanner = QuantumScanner(config)
                    scanner_name = "QuantumScanner"
                    self.phase_changed.emit("QuantumScanner initialized (180x+ faster)")
                except ImportError as e:
                    self.failed.emit(f"QuantumScanner not available: {e}\nInstall: pip install cupy-cuda12x torch pyzmq")
                    return
            
            if not scanner:
                self.failed.emit(f"Unknown scanner tier: {tier}")
                return
            
            # Phase: Discovery
            self.phase_changed.emit(f"{scanner_name}: Discovering files...")
            
            files_found = []
            groups_found = {}
            processed_count = 0
            total_size = 0
            
            # Scan files
            for file_meta in scanner.scan([root]):
                if self._cancelled:
                    self.cancelled.emit()
                    return
                
                processed_count += 1
                total_size += getattr(file_meta, 'size', 0)
                
                # Update progress every 100 files
                if processed_count % 100 == 0:
                    elapsed = time.perf_counter() - self._start_ts
                    progress = ScanProgress(
                        phase=f"Scanning with {scanner_name}",
                        message=f"Processed {processed_count:,} files",
                        percent=0.0,  # Unknown total
                        scanned_files=processed_count,
                        scanned_bytes=total_size,
                        elapsed_seconds=elapsed,
                        current_path=str(getattr(file_meta, 'path', '')),
                    )
                    self.progress_updated.emit(progress)
                    self.file_changed.emit(str(getattr(file_meta, 'path', '')))
                
                files_found.append(file_meta)
            
            # Phase: Exact duplicate grouping
            self.phase_changed.emit(f"{scanner_name}: Verifying duplicate groups...")
            groups = self._group_exact_duplicates(files_found)

            if self._cancelled:
                self.cancelled.emit()
                return

            # Phase: Complete
            elapsed = time.perf_counter() - self._start_ts
            self.phase_changed.emit(f"{scanner_name}: Completed")
            
            # Build result
            result = {
                "scan_root": str(root),
                "scan_name": self._cfg.scan_name or f"Scan of {root}",
                "file_count": processed_count,
                "total_size": total_size,
                "scan_duration": elapsed,
                "scanner_tier": tier,
                "scanner_name": scanner_name,
                "groups": groups,
                "group_count": len(groups),
                "groups_found": len(groups),
                "duplicate_count": sum(len(g.get("paths") or []) for g in groups),
                "cancelled": False,
            }
            
            # Final progress
            progress = ScanProgress(
                phase="Complete",
                message=f"Scanned {processed_count:,} files in {elapsed:.1f}s",
                percent=100.0,
                scanned_files=processed_count,
                scanned_bytes=total_size,
                elapsed_seconds=elapsed,
            )
            self.progress_updated.emit(progress)
            
            self.finished.emit(result)
            
        except Exception as e:
            msg = f"{e}"
            tb = traceback.format_exc()
            self.error_occurred.emit(msg)
            self.failed.emit(tb)

    def _group_exact_duplicates(self, files_found: List[Any]) -> List[Dict[str, Any]]:
        by_size: Dict[int, List[str]] = {}
        for file_meta in files_found:
            try:
                path = str(getattr(file_meta, "path", "") or "")
                size = int(getattr(file_meta, "size", 0) or 0)
            except Exception:
                continue
            if path and size >= int(self._cfg.min_size_bytes):
                by_size.setdefault(size, []).append(path)

        groups_by_hash: Dict[tuple[int, str], List[str]] = {}
        candidates = [(size, path) for size, paths in by_size.items() if len(paths) > 1 for path in paths]
        total = len(candidates)
        scanned_bytes = sum(size * len(paths) for size, paths in by_size.items())

        for idx, (size, path) in enumerate(candidates, start=1):
            if self._cancelled:
                break
            digest = self._full_hash_path(path)
            if not digest:
                continue
            groups_by_hash.setdefault((size, digest), []).append(path)

            if idx % 64 == 0 or idx == total:
                elapsed = max(0.0, time.perf_counter() - self._start_ts)
                self.progress_updated.emit(ScanProgress(
                    phase="Verifying duplicates",
                    message=f"Verified {idx:,}/{total:,} candidate files",
                    percent=0.0,
                    scanned_files=len(files_found),
                    scanned_bytes=scanned_bytes,
                    elapsed_seconds=elapsed,
                    current_path=path,
                ))

        groups: List[Dict[str, Any]] = []
        for (size, digest), paths in groups_by_hash.items():
            if len(paths) > 1:
                groups.append({
                    "hash": digest,
                    "size": size,
                    "paths": paths,
                    "count": len(paths),
                })
        return groups

    def _full_hash_path(self, path: str) -> Optional[str]:
        try:
            h = hashlib.md5()
            with open(path, "rb", buffering=0) as fp:
                while True:
                    chunk = fp.read(1024 * 1024)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None
