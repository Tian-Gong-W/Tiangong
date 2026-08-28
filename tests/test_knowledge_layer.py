from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tonmen.evidence import GraphNode
from tonmen.knowledge import (
    AttackPathSynthesizer,
    FreshnessState,
    KnowledgeCatalog,
    KnowledgeKind,
    KnowledgeQuery,
    KnowledgeRecord,
    KnowledgeStore,
    TargetProfile,
)
from tonmen.missions import MissionPlan, MissionRun


NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)


def _record(**overrides):
    data = {
        "kind": KnowledgeKind.THREAT_PATTERN,
        "title": "Current stack-specific research pattern",
        "summary": "Research context only; target evidence is still required.",
        "source": "vendor-advisory",
        "published_at": NOW - timedelta(days=3),
        "retrieved_at": NOW,
        "technologies": ("Next.js",),
        "required_products": ("endpoint_observation",),
        "preferred_modalities": ("http",),
        "max_age_days": 30,
    }
    data.update(overrides)
    return KnowledgeRecord.create(**data)


def test_freshness_first_weights_current_and_excludes_stale():
    current = _record(record_id="current")
    stale = _record(record_id="stale", published_at=NOW - timedelta(days=90))

    assert current.freshness_state(now=NOW) is FreshnessState.CURRENT
    assert stale.freshness_state(now=NOW) is FreshnessState.STALE

    matches = KnowledgeCatalog((current, stale)).query(
        KnowledgeQuery(technologies=("next.js",)),
        now=NOW,
    )
    assert [item.record.id for item in matches] == ["current"]


def test_knowledge_store_round_trips_records(tmp_path):
    store = KnowledgeStore.for_workspace(tmp_path)
    record = _record(record_id="stored")
    store.upsert(record)

    loaded = store.all()

    assert store.count() == 1
    assert loaded[0].id == "stored"
    assert loaded[0].technologies == ("Next.js",)


def test_target_profile_separates_observed_surface_scale_from_company_size():
    plan = MissionPlan.create("example.test", [])
    run = MissionRun.create(plan)
    run.graph.add_node(
        GraphNode(
            id="web:1",
            kind="intelligence.web",
            label="https://example.test",
            metadata={
                "target": "example.test",
                "data": {
                    "url": "https://example.test",
                    "technologies": ["Next.js", "Cloudflare"],
                },
            },
        )
    )

    profile = TargetProfile.from_run(run)

    assert profile.technologies == ("Next.js", "Cloudflare")
    assert profile.organization_scale.value == "unknown"
    assert profile.surface_scale.value == "small"


def test_attack_path_synthesizer_builds_chains_without_executing_them():
    first = _record(
        record_id="t1",
        kind=KnowledgeKind.TECHNIQUE,
        title="Condition A changes trust state",
        technique_id="A",
        enables=("B",),
        state_changes=("trust_state_changed",),
        required_products=("state_a_observation",),
    )
    second = _record(
        record_id="t2",
        kind=KnowledgeKind.TECHNIQUE,
        title="Condition B becomes reachable",
        technique_id="B",
        state_changes=("new_reachability",),
        required_products=("state_b_observation",),
    )
    matches = KnowledgeCatalog((first, second)).query(
        KnowledgeQuery(technologies=("Next.js",)),
        now=NOW,
    )

    paths = AttackPathSynthesizer().synthesize(matches)

    assert len(paths) == 1
    assert paths[0].knowledge_ids == ("t1", "t2")
    assert paths[0].required_products == ("state_a_observation", "state_b_observation")
