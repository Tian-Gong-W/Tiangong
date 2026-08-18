from __future__ import annotations

import json

import pytest

from tonmen.core.config import TonmenConfig
from tonmen.dashboard import DashboardState


def _state(tmp_path):
    return DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))


def test_console_audit_exposes_verified_chain_status(tmp_path):
    state = _state(tmp_path)
    assert state.runtime.audit is not None
    event = state.runtime.audit.append(
        action="tool.execute",
        tool="nmap",
        target="localhost",
        decision="allow",
        message="verified event",
        evidence_id="e-1",
    )

    payload = state.audit(20)

    assert payload["events"][-1]["id"] == event.id
    assert payload["integrity"]["valid"] is True
    assert payload["integrity"]["authenticated"] is True
    assert payload["integrity"]["events"] == 1
    assert payload["integrity"]["head_hash"] == event.event_hash


def test_console_refuses_to_display_tampered_authenticated_audit(tmp_path):
    state = _state(tmp_path)
    assert state.runtime.audit is not None
    state.runtime.audit.append(
        action="mission.start",
        tool="runtime",
        target="localhost",
        decision="allow",
        message="original",
    )
    path = tmp_path / "audit.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["message"] = "tampered"
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="audit integrity verification failed"):
        state.audit(20)
    with pytest.raises(RuntimeError, match="audit integrity verification failed"):
        state.guard()


def test_console_can_read_legacy_unauthenticated_audit_prefix_for_migration(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "legacy-1",
                "timestamp": "2026-08-18T00:00:00+00:00",
                "action": "legacy",
                "tool": "runtime",
                "target": "localhost",
                "decision": "allow",
                "message": "legacy event",
                "evidence_id": None,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    state = _state(tmp_path)

    payload = state.audit(20)

    assert payload["events"][0]["id"] == "legacy-1"
    assert payload["integrity"]["valid"] is True
    assert payload["integrity"]["authenticated"] is False
    assert payload["integrity"]["events"] == 1
