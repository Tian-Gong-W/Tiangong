from __future__ import annotations

from datetime import datetime, timezone

from tonmen.adaptive import AdaptiveParameterResolver, build_target_profile
from tonmen.evidence import EvidenceRecord, GraphNode
from tonmen.intelligence import FactKind, parse_evidence
from tonmen.missions import MissionPlan, MissionRun
from tonmen.tools import ToolRequest
from tonmen.tools.adapters import DnsIntelAdapter, TlsIntelAdapter


def _evidence(tool: str, target: str, stdout: str) -> EvidenceRecord:
    now = datetime.now(timezone.utc)
    return EvidenceRecord(
        id=f"e-{tool}",
        tool=tool,
        target=target,
        argv=(tool, target),
        exit_code=0,
        stdout=stdout,
        stderr="",
        started_at=now,
        finished_at=now,
    )


def test_dns_adapter_is_bounded_builtin_and_adaptive_only():
    adapter = DnsIntelAdapter()
    request = ToolRequest(tool="dns-intel", target="example.test")

    argv = adapter.build_argv(request)

    assert argv[1:3] == ("-m", "tonmen.tools.runners.dns_intel")
    assert argv[-2:] == ("--host", "example.test")
    assert adapter.readiness().ready is True
    assert adapter.spec.planning is not None
    assert adapter.spec.planning.include_in_baseline_envelope is False
    assert "dns.resolve" in adapter.spec.capabilities


def test_tls_adapter_adapts_to_observed_tls_port_but_remains_bounded():
    adapter = TlsIntelAdapter()
    request = ToolRequest(tool="tls-intel", target="example.test", parameters={"port": 443, "timeout": 8})

    parameters = adapter.adapt_parameters(
        request,
        {"ports": (80, 8443), "complexity": 4},
    )
    argv = adapter.build_argv(ToolRequest(tool="tls-intel", target="example.test", parameters=parameters))

    assert parameters["port"] == 8443
    assert 5 <= parameters["timeout"] <= 15
    assert argv[1:3] == ("-m", "tonmen.tools.runners.tls_intel")
    assert "8443" in argv
    assert adapter.spec.planning is not None
    assert adapter.spec.planning.include_in_baseline_envelope is False
    assert "certificate.inspect" in adapter.spec.capabilities


def test_dns_parser_records_positive_and_negative_resolution_as_facts():
    positive = parse_evidence(
        _evidence(
            "dns-intel",
            "example.test",
            '{"type":"dns","host":"example.test","record_type":"A","address":"192.0.2.10","resolved":true}\n',
        )
    )
    negative = parse_evidence(
        _evidence(
            "dns-intel",
            "missing.test",
            '{"type":"dns","host":"missing.test","record_type":"STATUS","resolved":false,"error":"not found"}\n',
        )
    )

    assert len(positive) == 1 and positive[0].kind is FactKind.DNS
    assert positive[0].data["address"] == "192.0.2.10"
    assert positive[0].data["resolved"] is True
    assert len(negative) == 1 and negative[0].kind is FactKind.DNS
    assert negative[0].data["resolved"] is False
    assert negative[0].data["error"] == "not found"


def test_tls_parser_records_certificate_metadata_and_negative_handshake():
    positive = parse_evidence(
        _evidence(
            "tls-intel",
            "example.test",
            '{"type":"tls","host":"example.test","port":443,"reachable":true,"version":"TLSv1.3",'
            '"cipher":"TLS_AES_256_GCM_SHA384","fingerprint_sha256":"abc","subject":"CN=example.test",'
            '"issuer":"CN=Example CA","sans":["example.test"]}\n',
        )
    )
    negative = parse_evidence(
        _evidence(
            "tls-intel",
            "example.test",
            '{"type":"tls","host":"example.test","port":443,"reachable":false,"error":"handshake failed"}\n',
        )
    )

    assert len(positive) == 1 and positive[0].kind is FactKind.TLS
    assert positive[0].data["version"] == "TLSv1.3"
    assert positive[0].data["sans"] == ["example.test"]
    assert len(negative) == 1 and negative[0].kind is FactKind.TLS
    assert negative[0].data["reachable"] is False
    assert negative[0].data["error"] == "handshake failed"


def test_target_profile_distinguishes_dns_and_tls_unknowns_semantically():
    plan = MissionPlan.create("https://example.test", [])
    run = MissionRun.create(plan)

    initial = build_target_profile(plan, run)
    assert initial.dns_resolution_needed is True
    assert initial.tls_probe_warranted is True
    assert "dns_identity" in initial.unknowns
    assert "tls_posture" in initial.unknowns

    run.graph.add_node(
        GraphNode(
            id="dns-1",
            kind="intelligence.dns",
            label="A example.test → 192.0.2.10",
            metadata={"data": {"address": "192.0.2.10", "resolved": True}},
        )
    )
    run.graph.add_node(
        GraphNode(
            id="tls-1",
            kind="intelligence.tls",
            label="TLS example.test:443 TLSv1.3",
            metadata={"data": {"port": 443, "reachable": True, "version": "TLSv1.3", "sans": ["example.test"]}},
        )
    )

    enriched = build_target_profile(plan, run)
    assert enriched.dns_resolution_needed is False
    assert enriched.tls_versions == ("TLSv1.3",)
    assert enriched.certificate_sans == ("example.test",)
    assert "dns_identity" not in enriched.unknowns
    assert "tls_posture" not in enriched.unknowns

    ip_plan = MissionPlan.create("192.0.2.10", [])
    ip_run = MissionRun.create(ip_plan)
    assert build_target_profile(ip_plan, ip_run).dns_resolution_needed is False


def test_resolver_profile_context_exposes_ports_for_tls_adapter():
    plan = MissionPlan.create("https://example.test", [])
    run = MissionRun.create(plan)
    run.graph.add_node(
        GraphNode(
            id="service-1",
            kind="intelligence.service",
            label="8443/tcp open https",
            metadata={"data": {"port": 8443, "service": "https"}},
        )
    )
    profile = AdaptiveParameterResolver().profile(plan, run)

    assert profile.tls_probe_warranted is True
    assert 8443 in profile.ports
