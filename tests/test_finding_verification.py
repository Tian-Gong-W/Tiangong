from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib import resources

from tonmen.evidence import EvidenceRecord
from tonmen.intelligence import parse_evidence, verify_nuclei_record
from tonmen.missions import MissionPlan, MissionRun, MissionRunState
from tonmen.reports import build_report, render_markdown


def _evidence(tool: str, stdout: str, *, target: str = "165252.cc") -> EvidenceRecord:
    now = datetime.now(timezone.utc)
    return EvidenceRecord(
        id=f"{tool}-evidence",
        tool=tool,
        target=target,
        argv=(tool, target),
        exit_code=0,
        stdout=stdout,
        stderr="",
        started_at=now,
        finished_at=now,
    )


def _nuclei_record(*, server: str = "kangle/3.5.19") -> dict:
    return {
        "template": "http/cves/2014/CVE-2014-2323.yaml",
        "template-id": "CVE-2014-2323",
        "template-path": "/home/wang/nuclei-templates/http/cves/2014/CVE-2014-2323.yaml",
        "info": {
            "name": "Lighttpd 1.4.34 SQL Injection and Path Traversal",
            "severity": "critical",
            "metadata": {"vendor": "lighttpd", "product": "lighttpd"},
            "classification": {
                "cve-id": ["cve-2014-2323"],
                "cpe": "cpe:2.3:a:lighttpd:lighttpd:*:*:*:*:*:*:*:*",
            },
        },
        "type": "http",
        "host": "165252.cc",
        "ip": "18.166.185.90",
        "port": "443",
        "scheme": "https",
        "url": "https://165252.cc",
        "matched-at": "https://165252.cc/etc/passwd",
        "matcher-status": True,
        "request": "GET /etc/passwd HTTP/1.1\r\nHost: [::1]' UNION SELECT '/\r\n\r\n",
        "response": (
            "HTTP/1.1 200 OK\r\n"
            f"Server: {server}\r\n"
            "Content-Type: text/plain\r\n\r\n"
            "root:x:0:0:root:/root:/bin/bash\n"
            "sshd:x:74:74:Privilege-separated SSH:/var/empty/sshd:/sbin/nologin\n"
        ),
    }


def _nmap_output() -> str:
    return """Starting Nmap 7.94SVN
Nmap scan report for 165252.cc (43.198.220.132)
Host is up (0.12s latency).
Other addresses for 165252.cc (not scanned): 18.166.185.90 43.198.193.28
PORT    STATE SERVICE
80/tcp  open  http
443/tcp open  https
Nmap done: 1 IP address (1 host up) scanned in 0.82 seconds
"""


def test_nuclei_match_can_confirm_evidence_while_contradicting_cve_attribution():
    verification = verify_nuclei_record(_nuclei_record())

    assert verification["template_status"] == "matched"
    assert verification["evidence_status"] == "confirmed"
    assert verification["evidence_strength"] == "strong"
    assert verification["observed_server"] == "kangle/3.5.19"
    assert verification["observed_ip"] == "18.166.185.90"
    assert verification["attribution_status"] == "contradicted"
    assert verification["confidence"] == 0.75
    assert "lighttpd" in verification["attribution_reasons"][0]


def test_matching_product_fingerprint_supports_attribution_without_changing_evidence_claim():
    verification = verify_nuclei_record(_nuclei_record(server="lighttpd/1.4.34"))

    assert verification["template_status"] == "matched"
    assert verification["evidence_status"] == "confirmed"
    assert verification["attribution_status"] == "supported"
    assert verification["confidence"] == 0.95


def test_intelligence_parser_persists_verification_and_backend_identity():
    nuclei = _evidence("nuclei", json.dumps(_nuclei_record()) + "\n")
    finding = parse_evidence(nuclei)[0]

    assert finding.kind.value == "finding"
    assert finding.confidence == 0.75
    assert finding.data["observed_ip"] == "18.166.185.90"
    assert finding.data["verification"]["evidence_status"] == "confirmed"
    assert finding.data["verification"]["attribution_status"] == "contradicted"


def test_nmap_parser_records_only_scanned_address_and_unscanned_dns_answers():
    facts = parse_evidence(_evidence("nmap", _nmap_output()))
    host = next(fact for fact in facts if fact.kind.value == "host")
    services = [fact for fact in facts if fact.kind.value == "service"]

    assert host.data["scanned_address"] == "43.198.220.132"
    assert host.data["other_resolved_addresses_not_scanned"] == ["18.166.185.90", "43.198.193.28"]
    assert {fact.data["port"] for fact in services} == {80, 443}
    assert all(fact.data["scanned_address"] == "43.198.220.132" for fact in services)


def test_report_scopes_nuclei_finding_to_different_resolved_backend():
    plan = MissionPlan.create("165252.cc", [])
    run = MissionRun.create(plan)
    run.evidence.extend(
        [
            _evidence("nmap", _nmap_output()),
            _evidence("nuclei", json.dumps(_nuclei_record()) + "\n"),
        ]
    )
    run.finish(MissionRunState.SUCCEEDED)

    report = build_report(plan, run)
    payload = report["executed_payloads"][0]

    assert report["schema"] == 2
    assert report["summary"]["template_matches"] == 1
    assert report["summary"]["evidence_confirmed"] == 1
    assert report["summary"]["attribution_supported"] == 0
    assert report["summary"]["attribution_contradicted"] == 1
    assert report["summary"]["backend_divergences"] == 1
    assert report["asset_correlation"]["nmap"]["scanned"] == ["43.198.220.132"]
    assert payload["verification"]["attribution_status"] == "contradicted"
    assert payload["backend_correlation"]["status"] == "different_resolved_backend"
    assert payload["backend_correlation"]["nuclei_ip"] == "18.166.185.90"
    assert payload["backend_correlation"]["nmap_scanned_addresses"] == ["43.198.220.132"]
    assert "do not generalize" in payload["backend_correlation"]["affected_scope"]

    markdown = render_markdown(report)
    assert "Template status: **matched**" in markdown
    assert "Evidence status: **confirmed**" in markdown
    assert "Attribution status: **contradicted**" in markdown
    assert "Backend correlation: **different_resolved_backend**" in markdown


def test_console_exposes_verification_matrix_and_report_status_layers():
    script = resources.files("tonmen.dashboard.static").joinpath("reports.js").read_text(encoding="utf-8")

    assert "Finding Verification Matrix" in script
    assert "Template ≠ Evidence ≠ Attribution" in script
    assert "backend_correlation" in script
    assert "Evidence confirmed" in script
    assert 'badge("Attribution"' in script
