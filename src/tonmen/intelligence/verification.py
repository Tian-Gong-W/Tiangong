from __future__ import annotations

import re
from typing import Any, Mapping

_PASSWD = re.compile(r"(?m)^root:[^:\r\n]*:0:0:[^\r\n]*$")
_SHADOW = re.compile(r"(?m)^root:[^:\r\n]+:\d+:")
_SERVER = re.compile(r"(?im)^Server:\s*([^\r\n]+)")


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _declared_products(item: Mapping[str, Any]) -> tuple[str, ...]:
    info = _as_mapping(item.get("info"))
    metadata = _as_mapping(info.get("metadata"))
    classification = _as_mapping(info.get("classification"))
    values: list[str] = []
    for key in ("vendor", "product"):
        value = metadata.get(key)
        if value:
            values.append(str(value).strip().lower())
    cpe = classification.get("cpe")
    if cpe:
        parts = str(cpe).split(":")
        if len(parts) > 4:
            values.extend(part.strip().lower() for part in parts[3:5] if part.strip() and part != "*")
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return tuple(unique)


def _observed_server(response: str) -> str | None:
    match = _SERVER.search(response or "")
    return match.group(1).strip() if match else None


def _strong_evidence(response: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if _PASSWD.search(response or ""):
        reasons.append("response contains a passwd-style root account record")
    if _SHADOW.search(response or ""):
        reasons.append("response contains a shadow-style root account record")
    return bool(reasons), reasons


def verify_nuclei_record(item: Mapping[str, Any]) -> dict[str, Any]:
    """Classify a Nuclei result without equating a template match with root-cause proof."""
    matcher = item.get("matcher-status")
    request = str(item.get("request") or "")
    response = str(item.get("response") or "")
    template_id = str(item.get("template-id") or item.get("templateID") or "")
    cve_template = template_id.upper().startswith("CVE-")
    products = _declared_products(item)
    server = _observed_server(response)

    template_status = "not_matched" if matcher is False else "matched"

    strong, evidence_reasons = _strong_evidence(response)
    if template_status != "matched":
        evidence_status = "not_confirmed"
        evidence_strength = "none"
    elif strong:
        evidence_status = "confirmed"
        evidence_strength = "strong"
    elif request and response:
        evidence_status = "observed"
        evidence_strength = "medium"
        evidence_reasons.append("executed request and response were captured")
    else:
        evidence_status = "matched_only"
        evidence_strength = "low"
        evidence_reasons.append("template matcher fired without captured request/response proof")

    attribution_reasons: list[str] = []
    if not cve_template:
        attribution_status = "not_applicable"
    elif not products:
        attribution_status = "unverified"
        attribution_reasons.append("CVE template has no product identity usable for correlation")
    elif not server:
        attribution_status = "unverified"
        attribution_reasons.append("response did not expose a Server fingerprint for product correlation")
    else:
        server_lower = server.lower()
        if any(product in server_lower for product in products):
            attribution_status = "supported"
            attribution_reasons.append(f"observed Server fingerprint {server!r} is consistent with declared product")
        else:
            attribution_status = "contradicted"
            attribution_reasons.append(
                f"observed Server fingerprint {server!r} does not match declared product(s): {', '.join(products)}"
            )

    confidence = 0.35
    if evidence_status == "observed":
        confidence = 0.65
    elif evidence_status == "confirmed":
        confidence = 0.9
    if attribution_status == "supported":
        confidence = min(1.0, confidence + 0.05)
    elif attribution_status == "contradicted":
        confidence = min(confidence, 0.75)
    confidence = round(confidence, 2)

    return {
        "template_status": template_status,
        "evidence_status": evidence_status,
        "evidence_strength": evidence_strength,
        "attribution_status": attribution_status,
        "confidence": confidence,
        "declared_products": list(products),
        "observed_server": server,
        "observed_ip": item.get("ip"),
        "matched_at": item.get("matched-at") or item.get("matched"),
        "evidence_reasons": evidence_reasons,
        "attribution_reasons": attribution_reasons,
        "note": "Template match, evidence confirmation, and CVE/root-cause attribution are separate claims.",
    }
