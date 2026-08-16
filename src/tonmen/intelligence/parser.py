from __future__ import annotations

import json
import re
from typing import Iterable

from tonmen.evidence import EvidenceRecord

from .model import FactKind, IntelligenceFact, Severity

_NMAP_SERVICE = re.compile(
    r"^(?P<port>\d+)\/(?P<protocol>tcp|udp)\s+open\s+(?P<service>\S+)(?:\s+(?P<detail>.*\S))?\s*$",
    re.IGNORECASE,
)
_HTTPX_URL = re.compile(r"^(?P<url>https?://\S+)")
_HTTPX_GROUP = re.compile(r"\[([^\]]*)\]")

_SEVERITY = {
    "info": Severity.INFO,
    "low": Severity.LOW,
    "medium": Severity.MEDIUM,
    "high": Severity.HIGH,
    "critical": Severity.CRITICAL,
}


def _nonempty_lines(text: str) -> Iterable[str]:
    for line in text.splitlines():
        value = line.strip()
        if value:
            yield value


def _parse_nmap(evidence: EvidenceRecord) -> list[IntelligenceFact]:
    facts: list[IntelligenceFact] = []
    host_seen = False
    for line in _nonempty_lines(evidence.stdout):
        if not host_seen and ("Host is up" in line or line.startswith("Nmap scan report for ")):
            host_seen = True
            facts.append(
                IntelligenceFact.create(
                    kind=FactKind.HOST,
                    source="nmap",
                    target=evidence.target,
                    title=f"Host observed: {evidence.target}",
                    evidence_id=evidence.id,
                    data={"state": "observed"},
                )
            )
        match = _NMAP_SERVICE.match(line)
        if not match:
            continue
        port = int(match.group("port"))
        protocol = match.group("protocol").lower()
        service = match.group("service")
        detail = (match.group("detail") or "").strip()
        title = f"{port}/{protocol} open {service}"
        if detail:
            title += f" ({detail})"
        facts.append(
            IntelligenceFact.create(
                kind=FactKind.SERVICE,
                source="nmap",
                target=evidence.target,
                title=title,
                evidence_id=evidence.id,
                data={
                    "port": port,
                    "protocol": protocol,
                    "state": "open",
                    "service": service,
                    "detail": detail,
                },
            )
        )
    return facts


def _parse_httpx(evidence: EvidenceRecord) -> list[IntelligenceFact]:
    facts: list[IntelligenceFact] = []
    for line in _nonempty_lines(evidence.stdout):
        match = _HTTPX_URL.search(line)
        if not match:
            continue
        url = match.group("url")
        groups = [item.strip() for item in _HTTPX_GROUP.findall(line)]
        status = None
        title = None
        technologies: list[str] = []
        remaining = list(groups)
        if remaining and remaining[0].isdigit():
            status = int(remaining.pop(0))
        if remaining:
            title = remaining.pop(0) or None
        if remaining:
            technologies = [part.strip() for part in remaining[-1].split(",") if part.strip()]
        label = url
        if status is not None:
            label += f" [{status}]"
        if title:
            label += f" {title}"
        facts.append(
            IntelligenceFact.create(
                kind=FactKind.WEB,
                source="httpx",
                target=evidence.target or url,
                title=label,
                evidence_id=evidence.id,
                data={
                    "url": url,
                    "status_code": status,
                    "title": title,
                    "technologies": technologies,
                },
            )
        )
    return facts


def _parse_nuclei(evidence: EvidenceRecord) -> list[IntelligenceFact]:
    facts: list[IntelligenceFact] = []
    for line in _nonempty_lines(evidence.stdout):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        info = item.get("info") if isinstance(item.get("info"), dict) else {}
        name = str(info.get("name") or item.get("template-id") or item.get("templateID") or "Nuclei finding")
        severity_text = str(info.get("severity") or "unknown").lower()
        severity = _SEVERITY.get(severity_text, Severity.UNKNOWN)
        matched = item.get("matched-at") or item.get("matched") or item.get("host") or evidence.target
        template_id = item.get("template-id") or item.get("templateID")
        facts.append(
            IntelligenceFact.create(
                kind=FactKind.FINDING,
                source="nuclei",
                target=str(matched) if matched is not None else evidence.target,
                title=name,
                evidence_id=evidence.id,
                severity=severity,
                data={
                    "template_id": template_id,
                    "matched_at": matched,
                    "type": item.get("type"),
                    "matcher_name": item.get("matcher-name") or item.get("matcher_name"),
                },
            )
        )
    return facts


def parse_evidence(evidence: EvidenceRecord) -> list[IntelligenceFact]:
    tool = evidence.tool.strip().lower()
    if tool == "nmap":
        return _parse_nmap(evidence)
    if tool == "httpx":
        return _parse_httpx(evidence)
    if tool == "nuclei":
        return _parse_nuclei(evidence)
    return []


def summarize_facts(source: str, facts: list[IntelligenceFact], fallback: str) -> str:
    if not facts:
        return fallback
    counts: dict[FactKind, int] = {}
    for fact in facts:
        counts[fact.kind] = counts.get(fact.kind, 0) + 1
    order = (FactKind.HOST, FactKind.SERVICE, FactKind.WEB, FactKind.FINDING)
    parts = [f"{counts[kind]} {kind.value}" for kind in order if counts.get(kind)]
    return f"{source}: " + ", ".join(parts)
