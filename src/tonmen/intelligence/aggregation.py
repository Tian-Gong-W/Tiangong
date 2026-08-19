from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

_SEVERITY_RANK = {
    "unknown": 0,
    "info": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "critical": 5,
}
_EVIDENCE_RANK = {"none": 0, "low": 1, "medium": 2, "strong": 3}
_EVIDENCE_STATUS_RANK = {"not_confirmed": 0, "matched_only": 1, "observed": 2, "confirmed": 3}


def _text(value: object) -> str:
    return str(value or "").strip()


def _identity(payload: Mapping[str, Any]) -> str:
    template_id = _text(payload.get("template_id") or payload.get("template-id") or payload.get("templateID"))
    if template_id:
        return template_id.lower()
    name = _text(payload.get("name"))
    matcher = _text(payload.get("matcher_name") or payload.get("matcher-name"))
    kind = _text(payload.get("type"))
    fallback = "|".join(part.lower() for part in (name, matcher, kind) if part)
    return fallback or "unidentified-finding"


def _backend(payload: Mapping[str, Any]) -> str:
    ip = _text(payload.get("ip"))
    if ip:
        return ip
    host = _text(payload.get("host"))
    if host:
        parsed = urlparse(host if "://" in host else f"//{host}")
        return parsed.hostname or host
    matched = _text(payload.get("matched_at") or payload.get("matched-at") or payload.get("url"))
    if matched:
        parsed = urlparse(matched if "://" in matched else f"//{matched}")
        return parsed.hostname or matched
    return "unknown"


def _request_fingerprint(payload: Mapping[str, Any]) -> str | None:
    request = _text(payload.get("request"))
    if not request:
        return None
    return hashlib.sha256(request.encode("utf-8", errors="replace")).hexdigest()[:16]


def _highest(values: Iterable[str], rank: Mapping[str, int], default: str) -> str:
    known = [value for value in values if value in rank]
    return max(known, key=lambda value: rank[value], default=default)


def _aggregate_attribution(values: Iterable[str]) -> str:
    states = {value for value in values if value}
    if not states or states == {"not_applicable"}:
        return "not_applicable"
    meaningful = states - {"not_applicable"}
    if len(meaningful) > 1:
        return "mixed"
    return next(iter(meaningful), "unverified")


def _aggregate_backend(name: str, instances: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_ids = list(dict.fromkeys(_text(item.get("evidence_id")) for item in instances if item.get("evidence_id")))
    locations = list(dict.fromkeys(_text(item.get("matched_at")) for item in instances if item.get("matched_at")))
    servers = list(dict.fromkeys(_text(item.get("observed_server")) for item in instances if item.get("observed_server")))
    request_fingerprints = list(
        dict.fromkeys(_text(item.get("request_fingerprint")) for item in instances if item.get("request_fingerprint"))
    )
    correlations = list(dict.fromkeys(_text(item.get("backend_status")) for item in instances if item.get("backend_status")))
    evidence_strength = _highest(
        (_text(item.get("evidence_strength")) for item in instances), _EVIDENCE_RANK, "none"
    )
    evidence_status = _highest(
        (_text(item.get("evidence_status")) for item in instances), _EVIDENCE_STATUS_RANK, "not_confirmed"
    )
    attribution_status = _aggregate_attribution(_text(item.get("attribution_status")) for item in instances)
    return {
        "backend": name,
        "instance_count": len(instances),
        "evidence_ids": evidence_ids,
        "matched_locations": locations,
        "observed_servers": servers,
        "request_fingerprints": request_fingerprints,
        "backend_correlation": correlations,
        "evidence_status": evidence_status,
        "evidence_strength": evidence_strength,
        "attribution_status": attribution_status,
        "confidence": round(max((float(item.get("confidence") or 0.0) for item in instances), default=0.0), 2),
    }


def aggregate_nuclei_findings(payloads: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Collapse repeated Nuclei observations into logical findings without losing backend provenance.

    The aggregate key is the template identity within one mission report. Individual IPs,
    evidence IDs, matched locations, request fingerprints and verification states remain
    attached as backend instances. Aggregation never implies that an unobserved DNS answer
    is affected.
    """
    groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_payloads: dict[str, list[Mapping[str, Any]]] = {}

    for payload in payloads:
        identity = _identity(payload)
        verification = payload.get("verification") if isinstance(payload.get("verification"), Mapping) else {}
        correlation = payload.get("backend_correlation") if isinstance(payload.get("backend_correlation"), Mapping) else {}
        instance = {
            "backend": _backend(payload),
            "evidence_id": payload.get("evidence_id"),
            "matched_at": payload.get("matched_at") or payload.get("matched-at") or payload.get("url"),
            "observed_server": verification.get("observed_server"),
            "template_status": verification.get("template_status"),
            "evidence_status": verification.get("evidence_status"),
            "evidence_strength": verification.get("evidence_strength"),
            "attribution_status": verification.get("attribution_status"),
            "confidence": verification.get("confidence"),
            "backend_status": correlation.get("status"),
            "request_fingerprint": _request_fingerprint(payload),
            "timestamp": payload.get("timestamp"),
        }
        groups.setdefault(identity, []).append(instance)
        source_payloads.setdefault(identity, []).append(payload)

    result: list[dict[str, Any]] = []
    for identity, instances in groups.items():
        payload_group = source_payloads[identity]
        first = payload_group[0]
        verification_states = [
            payload.get("verification") if isinstance(payload.get("verification"), Mapping) else {}
            for payload in payload_group
        ]
        backend_groups: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        for instance in instances:
            backend_groups.setdefault(_text(instance["backend"]) or "unknown", []).append(instance)
        backends = [_aggregate_backend(name, values) for name, values in backend_groups.items()]
        severity = _highest((_text(payload.get("severity")).lower() for payload in payload_group), _SEVERITY_RANK, "unknown")
        evidence_strength = _highest(
            (_text(item.get("evidence_strength")) for item in verification_states), _EVIDENCE_RANK, "none"
        )
        evidence_status = _highest(
            (_text(item.get("evidence_status")) for item in verification_states),
            _EVIDENCE_STATUS_RANK,
            "not_confirmed",
        )
        attribution_status = _aggregate_attribution(
            _text(item.get("attribution_status")) for item in verification_states
        )
        template_status = "matched" if any(_text(item.get("template_status")) == "matched" for item in verification_states) else "not_matched"
        evidence_ids = list(dict.fromkeys(_text(item.get("evidence_id")) for item in instances if item.get("evidence_id")))
        matched_locations = list(
            dict.fromkeys(_text(item.get("matched_at")) for item in instances if item.get("matched_at"))
        )
        observed_servers = list(
            dict.fromkeys(_text(item.get("observed_server")) for item in instances if item.get("observed_server"))
        )
        aggregate_id = hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()[:20]
        result.append(
            {
                "id": aggregate_id,
                "identity": identity,
                "template_id": first.get("template_id") or first.get("template-id") or first.get("templateID"),
                "name": first.get("name") or first.get("template_id") or identity,
                "severity": severity,
                "instance_count": len(instances),
                "duplicate_instance_count": max(0, len(instances) - 1),
                "unique_backend_count": len(backends),
                "affected_backends": backends,
                "evidence_ids": evidence_ids,
                "matched_locations": matched_locations,
                "observed_servers": observed_servers,
                "template_status": template_status,
                "evidence_status": evidence_status,
                "evidence_strength": evidence_strength,
                "attribution_status": attribution_status,
                "confidence": round(
                    max((float(item.get("confidence") or 0.0) for item in verification_states), default=0.0),
                    2,
                ),
                "backend_variance": len(backends) > 1 or len(observed_servers) > 1,
                "scope_note": (
                    "This is one logical finding with backend-specific evidence instances. "
                    "Only listed affected_backends are evidenced; other resolved addresses are not implied affected."
                ),
            }
        )
    return result
