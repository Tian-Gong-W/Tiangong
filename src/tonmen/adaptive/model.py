from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from tonmen.missions import MissionPlan, MissionRun

_COMMON_TLS_PORTS = {443, 8443, 9443, 465, 993, 995}
_TLS_SERVICE_MARKERS = ("https", "tls", "ssl", "imaps", "pop3s", "smtps")


@dataclass(frozen=True, slots=True)
class Hypothesis:
    key: str
    summary: str
    confidence: float
    basis_fact_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TargetProfile:
    target: str
    target_kind: str
    ports: tuple[int, ...]
    services: tuple[str, ...]
    dns_addresses: tuple[str, ...]
    tls_versions: tuple[str, ...]
    certificate_sans: tuple[str, ...]
    web_urls: tuple[str, ...]
    technologies: tuple[str, ...]
    findings: tuple[str, ...]
    severities: tuple[str, ...]
    unknowns: tuple[str, ...]
    hypotheses: tuple[Hypothesis, ...]
    complexity: int

    @property
    def has_web_surface(self) -> bool:
        return self.target_kind == "web" or bool(self.web_urls) or any("http" in service for service in self.services)

    @property
    def web_probe_warranted(self) -> bool:
        """Allow one bounded HTTP probe when Web evidence is positive or still unknown."""
        return self.has_web_surface or not self.services

    @property
    def dns_resolution_needed(self) -> bool:
        parsed = urlparse(self.target if "://" in self.target else f"scheme://{self.target}")
        host = parsed.hostname or ""
        if not host:
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            return not self.dns_addresses

    @property
    def tls_probe_warranted(self) -> bool:
        parsed = urlparse(self.target if "://" in self.target else f"scheme://{self.target}")
        if parsed.scheme == "https":
            return True
        if any(port in _COMMON_TLS_PORTS for port in self.ports):
            return True
        lowered = tuple(service.lower() for service in self.services)
        return any(any(marker in service for marker in _TLS_SERVICE_MARKERS) for service in lowered)

    @property
    def severe_findings(self) -> int:
        return sum(1 for severity in self.severities if severity in {"high", "critical"})


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _target_kind(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"scheme://{target}")
    if parsed.scheme in {"http", "https"}:
        return "web"
    return "host"


def build_target_profile(plan: MissionPlan, run: MissionRun) -> TargetProfile:
    if run.plan_id != plan.id:
        raise ValueError("mission run does not belong to this plan")

    ports: list[int] = []
    services: list[str] = []
    dns_addresses: list[str] = []
    tls_versions: list[str] = []
    certificate_sans: list[str] = []
    web_urls: list[str] = []
    technologies: list[str] = []
    findings: list[str] = []
    severities: list[str] = []
    service_fact_ids: list[str] = []
    dns_fact_ids: list[str] = []
    tls_fact_ids: list[str] = []
    web_fact_ids: list[str] = []
    finding_fact_ids: list[str] = []
    endpoint_coverage_observed = False

    for node in run.graph.nodes.values():
        data = node.metadata.get("data", {})
        if not isinstance(data, dict):
            data = {}

        if node.kind == "intelligence.service":
            service_fact_ids.append(node.id)
            service = str(data.get("service", "")).strip().lower()
            if service:
                services.append(service)
            raw_port = data.get("port")
            try:
                port = int(raw_port)
            except (TypeError, ValueError):
                port = 0
            if 1 <= port <= 65535:
                ports.append(port)

        elif node.kind == "intelligence.dns":
            dns_fact_ids.append(node.id)
            address = str(data.get("address") or "").strip()
            if address:
                dns_addresses.append(address)

        elif node.kind == "intelligence.tls":
            tls_fact_ids.append(node.id)
            version = str(data.get("version") or "").strip()
            if version:
                tls_versions.append(version)
            sans = data.get("sans", ())
            if isinstance(sans, (list, tuple)):
                certificate_sans.extend(str(value).strip() for value in sans if str(value).strip())
            raw_port = data.get("port")
            try:
                tls_port = int(raw_port)
            except (TypeError, ValueError):
                tls_port = 0
            if 1 <= tls_port <= 65535:
                ports.append(tls_port)

        elif node.kind == "intelligence.web":
            web_fact_ids.append(node.id)
            url = str(data.get("url") or node.metadata.get("target") or "").strip()
            if url:
                web_urls.append(url)
            if data.get("depth") is not None:
                endpoint_coverage_observed = True
            tech = data.get("technologies") or data.get("technology") or data.get("tech")
            if isinstance(tech, str):
                technologies.extend(part.strip().lower() for part in tech.replace("[", "").replace("]", "").split(","))
            elif isinstance(tech, (list, tuple)):
                technologies.extend(str(part).strip().lower() for part in tech)

        elif node.kind == "intelligence.finding":
            finding_fact_ids.append(node.id)
            findings.append(node.label)
            severities.append(str(node.metadata.get("severity", "info")).strip().lower())

    kind = _target_kind(plan.target)
    explicit_web = kind == "web"
    has_http_service = any("http" in service for service in services)
    has_web = explicit_web or bool(web_urls) or has_http_service

    provisional = TargetProfile(
        target=plan.target,
        target_kind=kind,
        ports=tuple(sorted(set(ports))),
        services=_unique(services),
        dns_addresses=_unique(dns_addresses),
        tls_versions=_unique(tls_versions),
        certificate_sans=_unique(certificate_sans),
        web_urls=_unique(web_urls),
        technologies=_unique(technologies),
        findings=_unique(findings),
        severities=_unique(severities),
        unknowns=(),
        hypotheses=(),
        complexity=1,
    )

    unknowns: list[str] = []
    if not service_fact_ids and not explicit_web:
        unknowns.append("network_surface")
    if provisional.dns_resolution_needed:
        unknowns.append("dns_identity")
    if provisional.tls_probe_warranted and not tls_fact_ids:
        unknowns.append("tls_posture")
    if has_web and not web_fact_ids:
        unknowns.append("web_reachability_and_technology")
    if web_fact_ids:
        if not endpoint_coverage_observed:
            unknowns.append("same_origin_endpoint_coverage")
        if not finding_fact_ids:
            unknowns.append("validation_coverage")
    if finding_fact_ids:
        unknowns.append("root_cause_and_impact")
        unknowns.append("remediation_confidence")

    hypotheses: list[Hypothesis] = []
    if provisional.tls_probe_warranted:
        basis = tuple((tls_fact_ids + service_fact_ids + web_fact_ids)[:16])
        hypotheses.append(
            Hypothesis(
                "tls_surface",
                "Target evidence supports a bounded TLS/certificate identity review.",
                0.9 if tls_fact_ids else 0.65,
                basis,
            )
        )
    if has_web:
        basis = tuple((web_fact_ids + service_fact_ids)[:16])
        hypotheses.append(Hypothesis("web_surface", "The target exposes an HTTP-capable surface worth deeper evidence-driven analysis.", 0.9 if web_fact_ids else 0.65, basis))
    lowered = " ".join(web_urls + technologies + findings)
    if any(token in lowered for token in ("graphql", "/api", "swagger", "openapi")):
        hypotheses.append(Hypothesis("api_surface", "Observed evidence suggests an API-oriented application surface.", 0.75, tuple(web_fact_ids[:16])))
    if finding_fact_ids:
        hypotheses.append(Hypothesis("risk_review", "Evidence-backed findings require root-cause, impact and remediation analysis; active end-stage actions remain disabled.", 0.8 if any(s in {"high", "critical"} for s in severities) else 0.65, tuple(finding_fact_ids[:16])))

    complexity = 1
    complexity += min(2, len(set(ports)) // 3)
    complexity += 1 if has_web else 0
    complexity += 1 if len(set(dns_addresses)) > 1 else 0
    complexity += 1 if tls_fact_ids else 0
    complexity += 1 if len(set(web_urls)) >= 5 else 0
    complexity += 1 if finding_fact_ids else 0
    complexity += 1 if any(s in {"high", "critical"} for s in severities) else 0
    complexity = max(1, min(5, complexity))

    return TargetProfile(
        target=plan.target,
        target_kind=kind,
        ports=tuple(sorted(set(ports))),
        services=_unique(services),
        dns_addresses=_unique(dns_addresses),
        tls_versions=_unique(tls_versions),
        certificate_sans=_unique(certificate_sans),
        web_urls=_unique(web_urls),
        technologies=_unique(technologies),
        findings=_unique(findings),
        severities=_unique(severities),
        unknowns=_unique(unknowns),
        hypotheses=tuple(hypotheses),
        complexity=complexity,
    )
