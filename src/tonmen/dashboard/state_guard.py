from __future__ import annotations


def install_verified_audit_reader(state_cls) -> None:
    """Require Audit HMAC verification before Console/API audit records are exposed."""
    if getattr(state_cls, "_tonmen_verified_audit_reader", False):
        return

    original_audit = state_cls.audit

    def verified_audit(self, limit: int = 200):
        audit_log = getattr(self.runtime, "audit", None)
        if audit_log is None:
            payload = original_audit(self, limit)
            payload["integrity"] = {
                "valid": True,
                "authenticated": False,
                "events": len(payload.get("events", [])),
                "head_hash": None,
            }
            return payload

        verification = audit_log.verify()
        if not verification.valid:
            detail = verification.error or "unknown integrity failure"
            raise RuntimeError(f"audit integrity verification failed: {detail}")

        payload = original_audit(self, limit)
        payload["integrity"] = {
            "valid": True,
            "authenticated": verification.authenticated,
            "events": verification.events,
            "head_hash": verification.head_hash,
        }
        return payload

    state_cls.audit = verified_audit
    state_cls._tonmen_verified_audit_reader = True
