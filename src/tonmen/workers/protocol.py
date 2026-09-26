from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass, replace
from typing import Any, Mapping
from uuid import uuid4

_WORKER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def normalize_worker_id(value: str) -> str:
    worker_id = str(value).strip().lower()
    if not _WORKER_ID_RE.fullmatch(worker_id):
        raise ValueError("worker id must match [a-z0-9][a-z0-9._-]{0,63}")
    return worker_id


def require_worker_secret(secret: str) -> str:
    value = str(secret or "")
    if len(value.encode("utf-8")) < 32:
        raise ValueError("worker shared secret must be at least 32 bytes")
    return value


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True, slots=True)
class DispatchEnvelope:
    version: int
    job_id: str
    worker_id: str
    nonce: str
    issued_at: int
    expires_at: int
    tool: str
    target: str | None
    parameters: Mapping[str, Any]
    context: Mapping[str, Any]
    approval_granted: bool
    control_decision: str
    control_reason: str
    signature: str = ""

    @classmethod
    def issue(
        cls,
        *,
        worker_id: str,
        tool: str,
        target: str | None,
        parameters: Mapping[str, Any],
        context: Mapping[str, Any],
        approval_granted: bool,
        control_decision: str,
        control_reason: str,
        secret: str,
        ttl_seconds: int = 60,
        now: int | None = None,
    ) -> "DispatchEnvelope":
        if not 5 <= int(ttl_seconds) <= 300:
            raise ValueError("worker job ttl must be between 5 and 300 seconds")
        issued = int(time.time() if now is None else now)
        envelope = cls(
            version=1,
            job_id=uuid4().hex,
            worker_id=normalize_worker_id(worker_id),
            nonce=secrets.token_urlsafe(18),
            issued_at=issued,
            expires_at=issued + int(ttl_seconds),
            tool=str(tool).strip().lower(),
            target=target,
            parameters=dict(parameters),
            context=dict(context),
            approval_granted=bool(approval_granted),
            control_decision=str(control_decision),
            control_reason=str(control_reason)[:500],
        )
        return envelope.sign(secret)

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "job_id": self.job_id,
            "worker_id": self.worker_id,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "tool": self.tool,
            "target": self.target,
            "parameters": dict(self.parameters),
            "context": dict(self.context),
            "approval_granted": self.approval_granted,
            "control_decision": self.control_decision,
            "control_reason": self.control_reason,
        }

    def sign(self, secret: str) -> "DispatchEnvelope":
        key = require_worker_secret(secret).encode("utf-8")
        digest = hmac.new(key, _canonical(self.unsigned_dict()), hashlib.sha256).hexdigest()
        return replace(self, signature=digest)

    def verify(
        self,
        secret: str,
        *,
        expected_worker_id: str,
        now: int | None = None,
        max_clock_skew_seconds: int = 30,
    ) -> None:
        if self.version != 1:
            raise ValueError("unsupported worker dispatch protocol version")
        if self.worker_id != normalize_worker_id(expected_worker_id):
            raise ValueError("dispatch is bound to a different worker")
        if not self.job_id or not self.nonce or not self.tool:
            raise ValueError("dispatch envelope is incomplete")
        current = int(time.time() if now is None else now)
        if self.issued_at > current + max_clock_skew_seconds:
            raise ValueError("dispatch issued_at is too far in the future")
        if self.expires_at <= current:
            raise ValueError("dispatch envelope expired")
        if self.expires_at - self.issued_at > 300:
            raise ValueError("dispatch ttl exceeds the protocol maximum")
        expected = self.sign(secret).signature
        if not self.signature or not hmac.compare_digest(self.signature, expected):
            raise ValueError("invalid worker dispatch signature")

    def as_dict(self) -> dict[str, Any]:
        payload = self.unsigned_dict()
        payload["signature"] = self.signature
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DispatchEnvelope":
        parameters = payload.get("parameters", {})
        context = payload.get("context", {})
        if not isinstance(parameters, dict) or not isinstance(context, dict):
            raise ValueError("dispatch parameters/context must be objects")
        return cls(
            version=int(payload.get("version", 0)),
            job_id=str(payload.get("job_id", "")),
            worker_id=normalize_worker_id(str(payload.get("worker_id", ""))),
            nonce=str(payload.get("nonce", "")),
            issued_at=int(payload.get("issued_at", 0)),
            expires_at=int(payload.get("expires_at", 0)),
            tool=str(payload.get("tool", "")).strip().lower(),
            target=payload.get("target") if payload.get("target") is None else str(payload.get("target")),
            parameters=dict(parameters),
            context=dict(context),
            approval_granted=bool(payload.get("approval_granted", False)),
            control_decision=str(payload.get("control_decision", "")),
            control_reason=str(payload.get("control_reason", ""))[:500],
            signature=str(payload.get("signature", "")),
        )
