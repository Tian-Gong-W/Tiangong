from __future__ import annotations

import json

import pytest

from tonmen.audit import AuditLog


def test_audit_events_form_a_verifiable_authenticated_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)

    first = log.append(
        action="tool.execute",
        tool="nmap",
        target="localhost",
        decision="allow",
        message="first",
    )
    second = log.append(
        action="tool.execute",
        tool="httpx",
        target="https://localhost",
        decision="allow",
        message="second",
        evidence_id="e-2",
    )

    verification = log.verify()
    assert verification.valid is True
    assert verification.authenticated is True
    assert verification.events == 2
    assert verification.head_hash == second.event_hash
    assert len(first.event_hash) == 64
    assert second.prev_hash == first.event_hash
    assert path.stat().st_mode & 0o077 == 0
    assert log.key_path.exists()
    assert log.key_path.stat().st_mode & 0o077 == 0
    assert len(log.key_path.read_bytes()) == 32


def test_audit_tampering_is_detected_and_blocks_future_append(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append(
        action="mission.start",
        tool="runtime",
        target="localhost",
        decision="allow",
        message="original",
    )
    log.append(
        action="mission.finish",
        tool="runtime",
        target="localhost",
        decision="allow",
        message="complete",
    )

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["message"] = "tampered"
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    verification = log.verify()
    assert verification.valid is False
    assert "hmac" in (verification.error or "").lower()
    with pytest.raises(RuntimeError, match="corrupted audit log"):
        log.append(
            action="mission.start",
            tool="runtime",
            target="localhost",
            decision="allow",
            message="must not append",
        )


def test_first_authenticated_event_anchors_entire_legacy_prefix(tmp_path):
    path = tmp_path / "audit.jsonl"
    legacy_rows = [
        {
            "id": "legacy-1",
            "timestamp": "2026-08-18T00:00:00+00:00",
            "action": "legacy",
            "tool": "runtime",
            "target": "localhost",
            "decision": "allow",
            "message": "one",
            "evidence_id": None,
        },
        {
            "id": "legacy-2",
            "timestamp": "2026-08-18T00:00:01+00:00",
            "action": "legacy",
            "tool": "runtime",
            "target": "localhost",
            "decision": "allow",
            "message": "two",
            "evidence_id": None,
        },
    ]
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in legacy_rows) + "\n", encoding="utf-8")
    log = AuditLog(path)

    chained = log.append(
        action="new",
        tool="runtime",
        target="localhost",
        decision="allow",
        message="anchored",
    )
    verification = log.verify()
    assert verification.valid is True
    assert verification.authenticated is True
    assert chained.prev_hash != "0" * 64

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["message"] = "legacy tampered"
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    verification = log.verify()
    assert verification.valid is False
    assert "previous hash mismatch" in (verification.error or "")


def test_missing_private_audit_key_makes_authenticated_log_unverifiable(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append(
        action="tool.execute",
        tool="nmap",
        target="localhost",
        decision="allow",
        message="recorded",
    )
    log.key_path.unlink()

    verification = log.verify()
    assert verification.valid is False
    assert "key is missing" in (verification.error or "")
