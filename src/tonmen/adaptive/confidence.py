from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from tonmen.missions import MissionPlan, MissionRun


class ClaimState(str, Enum):
    SUPPORTED = "supported"
    CONFLICTED = "conflicted"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class EvidenceClaim:
    """Evidence-backed claim posture derived from persisted Intelligence facts only."""

    key: str
    subject: str
    assertion: str | None
    state: ClaimState
    confidence: float
    support_fact_ids: tuple[str, ...] = ()
    conflict_fact_ids: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    observed_values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceConfidence:
    claims: tuple[EvidenceClaim, ...]

    @property
    def supported(self) -> tuple[EvidenceClaim, ...]:
        return tuple(item for item in self.claims if item.state is ClaimState.SUPPORTED)

    @property
    def conflicted(self) -> tuple[EvidenceClaim, ...]:
        return tuple(item for item in self.claims if item.state is ClaimState.CONFLICTED)

    @property
    def unresolved(self) -> tuple[EvidenceClaim, ...]:
        return tuple(item for item in self.claims if item.state is ClaimState.UNRESOLVED)

    @property
    def conflict_fact_ids(self) -> tuple[str, ...]:
        values: list[str] = []
        for claim in self.conflicted:
            values.extend(claim.support_fact_ids)
            values.extend(claim.conflict_fact_ids)
        return tuple(dict.fromkeys(values))[:32]


def _fact_nodes(run: MissionRun) -> list[Any]:
    return [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]


def _data(node: Any) -> dict[str, Any]:
    value = node.metadata.get("data", {})
    return value if isinstance(value, dict) else {}


def _confidence(node: Any) -> float:
    try:
        value = float(node.metadata.get("confidence", 1.0))
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, value))


def _source(node: Any) -> str:
    return str(node.metadata.get("source") or "unknown").strip().lower() or "unknown"


def _weighted_claim(key: str, subject: str, groups: dict[str, list[Any]]) -> EvidenceClaim:
    if not groups:
        return EvidenceClaim(key=key, subject=subject, assertion=None, state=ClaimState.UNRESOLVED, confidence=0.0)

    scores = {value: sum(max(0.05, _confidence(node)) for node in nodes) for value, nodes in groups.items()}
    assertion = sorted(scores, key=lambda value: (-scores[value], value))[0]
    support = groups[assertion]
    conflict = [node for value, nodes in groups.items() if value != assertion for node in nodes]
    support_weight = scores[assertion]
    total_weight = sum(scores.values()) or 1.0
    source_count = len({_source(node) for node in support})
    corroboration = min(1.0, 0.85 + max(0, source_count - 1) * 0.05)
    confidence = max(0.0, min(1.0, (support_weight / total_weight) * corroboration))
    state = ClaimState.CONFLICTED if conflict else ClaimState.SUPPORTED
    all_nodes = support + conflict
    return EvidenceClaim(
        key=key,
        subject=subject,
        assertion=assertion,
        state=state,
        confidence=round(confidence, 4),
        support_fact_ids=tuple(node.id for node in support),
        conflict_fact_ids=tuple(node.id for node in conflict),
        sources=tuple(dict.fromkeys(_source(node) for node in all_nodes)),
        observed_values=tuple(sorted(groups)),
    )


def _semantic_claim(key: str, subject: str, assertion: str, nodes: Iterable[Any]) -> EvidenceClaim:
    items = list(nodes)
    if not items:
        return EvidenceClaim(key=key, subject=subject, assertion=None, state=ClaimState.UNRESOLVED, confidence=0.0)
    average = sum(_confidence(node) for node in items) / len(items)
    sources = tuple(dict.fromkeys(_source(node) for node in items))
    corroboration = min(1.0, 0.9 + max(0, len(sources) - 1) * 0.05)
    return EvidenceClaim(
        key=key,
        subject=subject,
        assertion=assertion,
        state=ClaimState.SUPPORTED,
        confidence=round(min(1.0, average * corroboration), 4),
        support_fact_ids=tuple(node.id for node in items[:32]),
        sources=sources,
        observed_values=(assertion,),
    )


def assess_evidence_confidence(plan: MissionPlan, run: MissionRun) -> EvidenceConfidence:
    """Build conservative support/conflict posture from already-recorded facts.

    Conflicts require explicit comparable values for the same canonical subject. Missing
    evidence is never a contradiction. DNS multi-address answers are not treated as
    conflicting merely because multiple A/AAAA records exist; comparable DNS posture is
    resolution status. TLS version/fingerprint differences are recorded as observation
    conflicts, which may represent rotation, load balancing, negotiation or real change.
    API confidence is presence-oriented: bounded static endpoint/hint evidence supports
    an API-surface claim, while a clean negative inspection remains non-contradictory.
    """
    if run.plan_id != plan.id:
        raise ValueError("mission run does not belong to this plan")

    facts = _fact_nodes(run)
    claims: list[EvidenceClaim] = []

    web_support = []
    api_support = []
    finding_support = []
    service_groups: dict[tuple[str, int], dict[str, list[Any]]] = {}
    dns_resolution_groups: dict[str, dict[str, list[Any]]] = {}
    tls_reachability_groups: dict[tuple[str, int], dict[str, list[Any]]] = {}
    tls_version_groups: dict[tuple[str, int], dict[str, list[Any]]] = {}
    cert_fingerprint_groups: dict[tuple[str, int], dict[str, list[Any]]] = {}
    status_groups: dict[str, dict[str, list[Any]]] = {}
    severity_groups: dict[tuple[str, str], dict[str, list[Any]]] = {}

    for node in facts:
        data = _data(node)
        if node.kind == "intelligence.service":
            service = str(data.get("service") or "").strip().lower()
            protocol = str(data.get("protocol") or "tcp").strip().lower() or "tcp"
            try:
                port = int(data.get("port"))
            except (TypeError, ValueError):
                port = 0
            if service and 1 <= port <= 65535:
                service_groups.setdefault((protocol, port), {}).setdefault(service, []).append(node)
                if "http" in service:
                    web_support.append(node)

        elif node.kind == "intelligence.dns":
            host = str(data.get("host") or node.metadata.get("target") or "").strip().lower()
            if host and isinstance(data.get("resolved"), bool):
                value = "resolved" if data["resolved"] else "unresolved"
                dns_resolution_groups.setdefault(host, {}).setdefault(value, []).append(node)

        elif node.kind == "intelligence.tls":
            host = str(data.get("host") or node.metadata.get("target") or "").strip().lower()
            try:
                port = int(data.get("port") or 443)
            except (TypeError, ValueError):
                port = 443
            if host and 1 <= port <= 65535:
                if isinstance(data.get("reachable"), bool):
                    value = "reachable" if data["reachable"] else "unreachable"
                    tls_reachability_groups.setdefault((host, port), {}).setdefault(value, []).append(node)
                version = str(data.get("version") or "").strip()
                if version:
                    tls_version_groups.setdefault((host, port), {}).setdefault(version, []).append(node)
                fingerprint = str(data.get("fingerprint_sha256") or "").strip().lower()
                if fingerprint:
                    cert_fingerprint_groups.setdefault((host, port), {}).setdefault(fingerprint, []).append(node)

        elif node.kind == "intelligence.web":
            web_support.append(node)
            url = str(data.get("url") or node.metadata.get("target") or "").strip()
            status = data.get("status_code")
            if url and isinstance(status, int):
                status_groups.setdefault(url, {}).setdefault(str(status), []).append(node)
            lowered = f"{node.label} {data}".lower()
            if any(token in lowered for token in ("graphql", "/api", "swagger", "openapi")):
                api_support.append(node)

        elif node.kind == "intelligence.api":
            kind = str(data.get("kind") or "").strip().lower()
            if kind in {"endpoint", "hint"} and bool(data.get("observed", True)):
                api_support.append(node)
            elif kind == "summary":
                try:
                    endpoint_count = int(data.get("endpoint_count") or 0)
                except (TypeError, ValueError):
                    endpoint_count = 0
                hints = data.get("hints", ())
                if endpoint_count > 0 or (isinstance(hints, (list, tuple)) and any(str(item).strip() for item in hints)):
                    api_support.append(node)

        elif node.kind == "intelligence.finding":
            finding_support.append(node)
            target = str(node.metadata.get("target") or "").strip()
            severity = str(node.metadata.get("severity") or "unknown").strip().lower()
            severity_groups.setdefault((target, node.label), {}).setdefault(severity, []).append(node)

    claims.append(_semantic_claim("web_surface", "Web surface exists", "observed", web_support))
    claims.append(_semantic_claim("api_surface", "API-oriented surface exists", "observed", api_support))
    claims.append(_semantic_claim("risk_review", "Evidence-backed finding requires review", "observed", finding_support))

    for (protocol, port), groups in sorted(service_groups.items()):
        claims.append(_weighted_claim(f"service_identity:{protocol}:{port}", f"Service identity {port}/{protocol}", groups))
    for host, groups in sorted(dns_resolution_groups.items()):
        claims.append(_weighted_claim(f"dns_resolution:{host}", f"DNS resolution {host}", groups))
    for (host, port), groups in sorted(tls_reachability_groups.items()):
        claims.append(_weighted_claim(f"tls_reachability:{host}:{port}", f"TLS reachability {host}:{port}", groups))
    for (host, port), groups in sorted(tls_version_groups.items()):
        claims.append(_weighted_claim(f"tls_version:{host}:{port}", f"TLS negotiated version {host}:{port}", groups))
    for (host, port), groups in sorted(cert_fingerprint_groups.items()):
        claims.append(_weighted_claim(f"certificate_fingerprint:{host}:{port}", f"Certificate fingerprint {host}:{port}", groups))
    for url, groups in sorted(status_groups.items()):
        claims.append(_weighted_claim(f"web_status:{url}", f"HTTP status {url}", groups))
    for (target, label), groups in sorted(severity_groups.items()):
        subject = f"Finding severity {label}" + (f" @ {target}" if target else "")
        claims.append(_weighted_claim(f"finding_severity:{target}:{label}", subject, groups))

    return EvidenceConfidence(tuple(claims))
