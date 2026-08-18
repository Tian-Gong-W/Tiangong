from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

_GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    timestamp: datetime
    action: str
    tool: str
    target: str | None
    decision: str
    message: str
    evidence_id: str | None = None
    prev_hash: str = ""
    event_hash: str = ""


@dataclass(frozen=True, slots=True)
class AuditVerification:
    valid: bool
    events: int
    head_hash: str
    error: str | None = None


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _legacy_digest(previous: str, payload: dict[str, Any]) -> str:
    """Anchor pre-chain JSONL records into the first chained event.

    Legacy events had no stored hash, so they cannot prove their own historical state.
    Folding the entire legacy prefix into the first new `prev_hash` means any later
    mutation of that prefix becomes detectable once at least one chained event exists.
    """
    digest = hashlib.sha256()
    digest.update(previous.encode("ascii"))
    digest.update(b"\n")
    digest.update(_canonical(payload))
    return digest.hexdigest()


def _event_digest(payload: dict[str, Any]) -> str:
    body = {key: value for key, value in payload.items() if key != "event_hash"}
    return hashlib.sha256(_canonical(body)).hexdigest()


class AuditLog:
    """Append-only, tamper-evident JSONL audit log.

    Raw scanner output lives in Evidence, not audit. New records form a SHA-256 chain.
    Append verifies the existing chain first and refuses to extend a corrupted log.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()

    def _chain_state(self) -> AuditVerification:
        if not self.path.exists():
            return AuditVerification(True, 0, _GENESIS_HASH)

        previous = _GENESIS_HASH
        count = 0
        chained_seen = False
        try:
            lines = self.path.read_text(encoding="utf-8", errors="strict").splitlines()
        except (OSError, UnicodeError) as exc:
            return AuditVerification(False, 0, previous, f"audit log unreadable: {exc}")

        for line_number, raw in enumerate(lines, start=1):
            if not raw.strip():
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                return AuditVerification(False, count, previous, f"invalid JSON at line {line_number}: {exc.msg}")
            if not isinstance(payload, dict):
                return AuditVerification(False, count, previous, f"non-object audit event at line {line_number}")

            has_prev = "prev_hash" in payload
            has_event = "event_hash" in payload
            if has_prev or has_event:
                if not (has_prev and has_event):
                    return AuditVerification(False, count, previous, f"incomplete hash fields at line {line_number}")
                chained_seen = True
                prev_hash = str(payload.get("prev_hash") or "")
                event_hash = str(payload.get("event_hash") or "")
                if len(prev_hash) != 64 or len(event_hash) != 64:
                    return AuditVerification(False, count, previous, f"invalid hash length at line {line_number}")
                if not hmac.compare_digest(prev_hash, previous):
                    return AuditVerification(False, count, previous, f"previous hash mismatch at line {line_number}")
                expected = _event_digest(payload)
                if not hmac.compare_digest(event_hash, expected):
                    return AuditVerification(False, count, previous, f"event hash mismatch at line {line_number}")
                previous = event_hash
            else:
                if chained_seen:
                    return AuditVerification(False, count, previous, f"legacy record after chained record at line {line_number}")
                previous = _legacy_digest(previous, payload)
            count += 1

        return AuditVerification(True, count, previous)

    def verify(self) -> AuditVerification:
        with self._lock:
            return self._chain_state()

    def append(
        self,
        *,
        action: str,
        tool: str,
        target: str | None,
        decision: str,
        message: str,
        evidence_id: str | None = None,
    ) -> AuditEvent:
        with self._lock:
            verification = self._chain_state()
            if not verification.valid:
                raise RuntimeError(f"refusing to append to corrupted audit log: {verification.error}")

            event_id = uuid4().hex
            timestamp = datetime.now(timezone.utc)
            payload: dict[str, Any] = {
                "id": event_id,
                "timestamp": timestamp.isoformat(),
                "action": action,
                "tool": tool,
                "target": target,
                "decision": decision,
                "message": message,
                "evidence_id": evidence_id,
                "prev_hash": verification.head_hash,
            }
            payload["event_hash"] = _event_digest(payload)
            event = AuditEvent(
                id=event_id,
                timestamp=timestamp,
                action=action,
                tool=tool,
                target=target,
                decision=decision,
                message=message,
                evidence_id=evidence_id,
                prev_hash=payload["prev_hash"],
                event_hash=payload["event_hash"],
            )

            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
            return event
