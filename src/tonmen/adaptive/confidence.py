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
        return EvidenceClaim(
            key=key,
            subject=subject,
            assertion=None,
            state=ClaimState.UNRESOLVED,
            confidence=0.0,
        )

    scores = {
        value: sum(max(0.05, _confidence(node)) for node in nodes)
        for value, nodes in groups.items()
    }
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
        return EvidenceClaim(
            key=key,
            subject=subject,
            assertion=None,
            state=ClaimState.UNRESOLVED,
            confidence=0.0,
        )
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

    A conflict is recorded only when comparable facts assert different explicit values
    for the same canonical subject (for example service identity on the same port,
    HTTP status for the same URL, or severity for the same named finding). Absence of
    evidence is never treated as contradictory evidence.
    """
    if run.plan_id != plan.id:
        raise ValueError("mission run does not belong to this plan")

    facts = _fact_nodes(run)
    claims: list[EvidenceClaim] = []

    web_support = []
    api_support = []
    finding_support = []
    service_groups: dict[tuple[str, int], dict[str, list[Any]]] = {}
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

        elif node.kind == "intelligence.web":
            web_support.append(node)
            url = str(data.get("url") or node.metadata.get("target") or "").strip()
            status = data.get("status_code")
            if url and isinstance(status, int):
                status_groups.setdefault(url, {}).setdefault(str(status), []).append(node)
            lowered = f"{node.label} {data}".lower()
            if any(token in lowered for token in ("graphql", "/api", "swagger", "openapi")):
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
    for url, groups in sorted(status_groups.items()):
        claims.append(_weighted_claim(f"web_status:{url}", f"HTTP status {url}", groups))
    for (target, label), groups in sorted(severity_groups.items()):
        subject = f"Finding severity {label}" + (f" @ {target}" if target else "")
        claims.append(_weighted_claim(f"finding_severity:{target}:{label}", subject, groups))

    return EvidenceConfidence(tuple(claims))
