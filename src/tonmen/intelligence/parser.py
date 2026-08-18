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


def _parse_dns_intel(evidence: EvidenceRecord) -> list[IntelligenceFact]:
    facts: list[IntelligenceFact] = []
    for line in _nonempty_lines(evidence.stdout):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict) or item.get("type") != "dns":
            continue
        host = str(item.get("host") or evidence.target or "").strip()
        record_type = str(item.get("record_type") or "STATUS").upper()
        address = str(item.get("address") or "").strip()
        resolved = bool(item.get("resolved", bool(address)))
        if address:
            title = f"{record_type} {host} → {address}"
        else:
            title = f"DNS unresolved: {host}"
        facts.append(
            IntelligenceFact.create(
                kind=FactKind.DNS,
                source="dns-intel",
                target=host or evidence.target,
                title=title,
                evidence_id=evidence.id,
                confidence=1.0 if resolved else 0.9,
                data={
                    "host": host,
                    "record_type": record_type,
                    "address": address or None,
                    "canonical_name": item.get("canonical_name"),
                    "reverse_name": item.get("reverse_name"),
                    "resolved": resolved,
                    "error": item.get("error"),
                },
            )
        )
    return facts


def _parse_tls_intel(evidence: EvidenceRecord) -> list[IntelligenceFact]:
    facts: list[IntelligenceFact] = []
    for line in _nonempty_lines(evidence.stdout):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict) or item.get("type") != "tls":
            continue
        host = str(item.get("host") or evidence.target or "").strip()
        try:
            port = int(item.get("port") or 443)
        except (TypeError, ValueError):
            port = 443
        reachable = bool(item.get("reachable", False))
        version = str(item.get("version") or "").strip()
        cipher = str(item.get("cipher") or "").strip()
        if reachable:
            title = f"TLS {host}:{port}"
            if version:
                title += f" {version}"
            if cipher:
                title += f" {cipher}"
        else:
            title = f"TLS handshake unavailable: {host}:{port}"
        sans = item.get("sans", ())
        safe_sans = [str(value)[:255] for value in sans[:128]] if isinstance(sans, list) else []
        facts.append(
            IntelligenceFact.create(
                kind=FactKind.TLS,
                source="tls-intel",
                target=host or evidence.target,
                title=title,
                evidence_id=evidence.id,
                confidence=1.0 if reachable else 0.9,
                data={
                    "host": host,
                    "port": port,
                    "reachable": reachable,
                    "version": version or None,
                    "cipher": cipher or None,
                    "cipher_bits": item.get("cipher_bits"),
                    "fingerprint_sha256": item.get("fingerprint_sha256"),
                    "subject": item.get("subject"),
                    "issuer": item.get("issuer"),
                    "serial_number": item.get("serial_number"),
                    "not_before": item.get("not_before"),
                    "not_after": item.get("not_after"),
                    "sans": safe_sans,
                    "error": item.get("error"),
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


def _parse_api_intel(evidence: EvidenceRecord) -> list[IntelligenceFact]:
    facts: list[IntelligenceFact] = []
    for line in _nonempty_lines(evidence.stdout):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "api":
            kind = str(item.get("kind") or "").strip().lower()
            if kind == "endpoint":
                endpoint = str(item.get("endpoint") or "").strip()
                absolute_url = str(item.get("absolute_url") or "").strip()
                if not endpoint and not absolute_url:
                    continue
                label = endpoint or absolute_url
                facts.append(
                    IntelligenceFact.create(
                        kind=FactKind.API,
                        source="api-intel",
                        target=absolute_url or evidence.target,
                        title=f"API endpoint observed: {label[:512]}",
                        evidence_id=evidence.id,
                        confidence=0.9,
                        data={
                            "kind": "endpoint",
                            "endpoint": endpoint or None,
                            "absolute_url": absolute_url or None,
                            "source": item.get("source"),
                            "source_url": item.get("source_url"),
                            "observed": True,
                            "javascript_executed": False,
                        },
                    )
                )
            elif kind == "hint":
                hint = str(item.get("hint") or "").strip().lower()
                if not hint:
                    continue
                facts.append(
                    IntelligenceFact.create(
                        kind=FactKind.API,
                        source="api-intel",
                        target=str(item.get("url") or evidence.target or "") or evidence.target,
                        title=f"API technology hint observed: {hint}",
                        evidence_id=evidence.id,
                        confidence=0.8,
                        data={"kind": "hint", "hint": hint, "observed": True, "javascript_executed": False},
                    )
                )
        elif item_type == "api_summary":
            hints = item.get("hints", ())
            safe_hints = [str(value).strip().lower()[:64] for value in hints[:32]] if isinstance(hints, list) else []
            endpoint_count = item.get("endpoint_count")
            try:
                endpoint_count = max(0, int(endpoint_count))
            except (TypeError, ValueError):
                endpoint_count = 0
            entry_reachable = bool(item.get("entry_reachable", False))
            facts.append(
                IntelligenceFact.create(
                    kind=FactKind.API,
                    source="api-intel",
                    target=str(item.get("url") or evidence.target or "") or evidence.target,
                    title=(
                        f"API static intelligence completed: {endpoint_count} endpoint candidate(s)"
                        if entry_reachable
                        else "API static intelligence completed: entry unavailable"
                    ),
                    evidence_id=evidence.id,
                    confidence=1.0 if entry_reachable else 0.9,
                    data={
                        "kind": "summary",
                        "inspected": True,
                        "entry_reachable": entry_reachable,
                        "endpoint_count": endpoint_count,
                        "scripts_discovered": item.get("scripts_discovered"),
                        "scripts_fetched": item.get("scripts_fetched"),
                        "hints": safe_hints,
                        "javascript_executed": False,
                        "forms_submitted": False,
                        "cross_origin_fetches": False,
                    },
                )
            )
    return facts


def _crawler_security_findings(evidence: EvidenceRecord, item: dict, url: str) -> list[IntelligenceFact]:
    security = item.get("security")
    if not isinstance(security, dict) or item.get("depth") != 0:
        return []

    facts: list[IntelligenceFact] = []

    def add(title: str, severity: Severity, issue: str, **data) -> None:
        facts.append(
            IntelligenceFact.create(
                kind=FactKind.FINDING,
                source="crawler",
                target=url,
                title=title,
                evidence_id=evidence.id,
                confidence=0.95,
                severity=severity,
                data={"issue": issue, "passive": True, **data},
            )
        )

    is_https = bool(security.get("https"))
    if is_https and security.get("hsts") is False:
        add("HSTS header not observed on HTTPS entry page", Severity.LOW, "hsts_missing")

    if security.get("csp") is False:
        add("Content-Security-Policy header not observed on entry page", Severity.INFO, "csp_missing")

    cookies = security.get("cookies")
    if isinstance(cookies, list):
        for cookie in cookies[:64]:
            if not isinstance(cookie, dict):
                continue
            name = str(cookie.get("name") or "cookie")[:128]
            missing: list[str] = []
            if is_https and cookie.get("secure") is False:
                missing.append("Secure")
            if cookie.get("httponly") is False:
                missing.append("HttpOnly")
            if cookie.get("samesite") in {None, ""}:
                missing.append("SameSite")
            if missing:
                add(
                    f"Cookie policy gap: {name} missing {', '.join(missing)}",
                    Severity.LOW,
                    "cookie_policy",
                    cookie_name=name,
                    missing_flags=missing,
                    cookie_value_recorded=False,
                )

    allow_origin = security.get("cors_allow_origin")
    if allow_origin == "*":
        credentials = bool(security.get("cors_allow_credentials"))
        add(
            "CORS wildcard origin response observed" + (" with credentials flag" if credentials else ""),
            Severity.LOW if credentials else Severity.INFO,
            "cors_wildcard",
            allow_origin="*",
            allow_credentials=credentials,
        )

    return facts


def _parse_crawler(evidence: EvidenceRecord) -> list[IntelligenceFact]:
    facts: list[IntelligenceFact] = []
    for line in _nonempty_lines(evidence.stdout):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict) or item.get("type") != "page":
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url:
            continue
        status = item.get("status")
        title = item.get("title")
        label = url
        if isinstance(status, int):
            label += f" [{status}]"
        if title:
            label += f" {title}"
        security = item.get("security") if isinstance(item.get("security"), dict) else None
        facts.append(
            IntelligenceFact.create(
                kind=FactKind.WEB,
                source="crawler",
                target=url,
                title=label,
                evidence_id=evidence.id,
                data={
                    "url": url,
                    "status_code": status,
                    "title": title,
                    "content_type": item.get("content_type"),
                    "depth": item.get("depth"),
                    "bytes": item.get("bytes"),
                    "truncated": bool(item.get("truncated", False)),
                    "redirected": bool(item.get("redirected", False)),
                    "security": security,
                },
            )
        )
        facts.extend(_crawler_security_findings(evidence, item, url))
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
    if tool == "dns-intel":
        return _parse_dns_intel(evidence)
    if tool == "tls-intel":
        return _parse_tls_intel(evidence)
    if tool == "httpx":
        return _parse_httpx(evidence)
    if tool == "api-intel":
        return _parse_api_intel(evidence)
    if tool == "crawler":
        return _parse_crawler(evidence)
    if tool == "nuclei":
        return _parse_nuclei(evidence)
    return []


def summarize_facts(source: str, facts: list[IntelligenceFact], fallback: str) -> str:
    if not facts:
        return fallback
    counts: dict[FactKind, int] = {}
    for fact in facts:
        counts[fact.kind] = counts.get(fact.kind, 0) + 1
    order = (FactKind.HOST, FactKind.SERVICE, FactKind.DNS, FactKind.TLS, FactKind.WEB, FactKind.API, FactKind.FINDING)
    parts = [f"{counts[kind]} {kind.value}" for kind in order if counts.get(kind)]
    return f"{source}: " + ", ".join(parts)
