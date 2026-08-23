from __future__ import annotations

from tonmen.adaptive import ClaimState, assess_evidence_confidence
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun


def test_dns_resolution_change_is_an_explicit_observation_conflict():
    plan = MissionPlan.create("example.test", [])
    run = MissionRun.create(plan)
    run.graph.add_node(
        GraphNode(
            id="dns-up",
            kind="intelligence.dns",
            label="A example.test → 192.0.2.10",
            metadata={"source": "dns-intel", "target": "example.test", "confidence": 1.0,
                      "data": {"host": "example.test", "resolved": True, "address": "192.0.2.10"}},
        )
    )
    run.graph.add_node(
        GraphNode(
            id="dns-down",
            kind="intelligence.dns",
            label="DNS unresolved: example.test",
            metadata={"source": "dns-intel", "target": "example.test", "confidence": 0.9,
                      "data": {"host": "example.test", "resolved": False}},
        )
    )

    assessment = assess_evidence_confidence(plan, run)
    claim = next(item for item in assessment.claims if item.key == "dns_resolution:example.test")

    assert claim.state is ClaimState.CONFLICTED
    assert set(claim.observed_values) == {"resolved", "unresolved"}
    assert set(claim.support_fact_ids + claim.conflict_fact_ids) == {"dns-up", "dns-down"}


def test_multiple_dns_addresses_do_not_create_a_false_conflict():
    plan = MissionPlan.create("example.test", [])
    run = MissionRun.create(plan)
    for index, address in enumerate(("192.0.2.10", "192.0.2.11"), start=1):
        run.graph.add_node(
            GraphNode(
                id=f"dns-{index}",
                kind="intelligence.dns",
                label=f"A example.test → {address}",
                metadata={"source": "dns-intel", "target": "example.test", "confidence": 1.0,
                          "data": {"host": "example.test", "resolved": True, "address": address}},
            )
        )

    assessment = assess_evidence_confidence(plan, run)
    claim = next(item for item in assessment.claims if item.key == "dns_resolution:example.test")

    assert claim.state is ClaimState.SUPPORTED
    assert claim.observed_values == ("resolved",)
    assert not claim.conflict_fact_ids


def test_tls_version_change_is_recorded_without_declaring_which_value_is_wrong():
    plan = MissionPlan.create("https://example.test", [])
    run = MissionRun.create(plan)
    for index, version in enumerate(("TLSv1.2", "TLSv1.3"), start=1):
        run.graph.add_node(
            GraphNode(
                id=f"tls-{index}",
                kind="intelligence.tls",
                label=f"TLS example.test:443 {version}",
                metadata={"source": "tls-intel", "target": "example.test", "confidence": 1.0,
                          "data": {"host": "example.test", "port": 443, "reachable": True,
                                   "version": version, "fingerprint_sha256": "same-cert"}},
            )
        )

    assessment = assess_evidence_confidence(plan, run)
    version = next(item for item in assessment.claims if item.key == "tls_version:example.test:443")
    fingerprint = next(item for item in assessment.claims if item.key == "certificate_fingerprint:example.test:443")

    assert version.state is ClaimState.CONFLICTED
    assert set(version.observed_values) == {"TLSv1.2", "TLSv1.3"}
    assert fingerprint.state is ClaimState.SUPPORTED
    assert fingerprint.observed_values == ("same-cert",)
