from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, filename: str):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_deletion_gate_issues_and_consumes_token() -> None:
    gate_mod = _load("deletion_gate", "deletion_gate.py")
    gate = gate_mod.DeletionGate()
    token = gate.issue_token("ci")
    assert gate.verify_token(token)
    gate.assert_allowed(validation_mode=False, token=token)
    # consumed
    assert not gate.verify_token(token)


def test_deletion_gate_rejects_empty_token() -> None:
    gate_mod = _load("deletion_gate", "deletion_gate.py")
    gate = gate_mod.DeletionGate()
    try:
        gate.assert_allowed(validation_mode=False, token=None)
    except gate_mod.DeletionGateError:
        pass
    else:
        raise AssertionError("expected DeletionGateError")


def test_deletion_gate_accepts_uuid_hex_fallback() -> None:
    gate_mod = _load("deletion_gate", "deletion_gate.py")
    gate = gate_mod.DeletionGate()
    uuid_hex = "a" * 32
    assert gate.verify_token(uuid_hex)


def test_scan_history_roundtrip() -> None:
    models = _load("models", "models.py")
    entry = models.ScanHistoryEntry(
        scan_id="s1",
        name="desktop",
        root_path="/tmp",
        status=models.ScanStatus.COMPLETED,
        result_summary=models.ScanResultSummary(scanned_files=10, items=2),
        duration_ms=1000,
    )
    restored = models.ScanHistoryEntry.from_dict(entry.to_dict())
    assert restored.scan_id == "s1"
    assert restored.status is models.ScanStatus.COMPLETED
    assert restored.result_summary.scanned_files == 10
    assert restored.get_efficiency_score() > 0
