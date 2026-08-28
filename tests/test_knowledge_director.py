from __future__ import annotations

from datetime import datetime, timezone

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.knowledge import KnowledgeKind, KnowledgeRecord, KnowledgeStore
from tonmen.missions import MissionRun, MissionRunState
from tonmen.reasoning import MissionDirector


def test_fresh_knowledge_can_prioritize_evidence_need_without_becoming_fact(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    plan = MissionPlanner(runtime).plan("localhost")
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING
    run.graph.add_node(
        GraphNode(
            id="web:localhost",
            kind="intelligence.web",
            label="http://localhost",
            metadata={
                "target": "localhost",
                "data": {
                    "url": "http://localhost",
                    "status_code": 200,
                    "technologies": ["Next.js"],
                },
            },
        )
    )

    KnowledgeStore.for_workspace(tmp_path).upsert(
        KnowledgeRecord.create(
            record_id="fresh-next",
            kind=KnowledgeKind.PRODUCT_CHANGE,
            title="Recent Next.js research context",
            summary="Current product context that justifies endpoint evidence.",
            source="vendor-advisory",
            published_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
            retrieved_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
            technologies=("Next.js",),
            required_products=("endpoint_observation",),
            preferred_modalities=("http",),
            max_age_days=30,
        )
    )

    director = MissionDirector(runtime)
    request = director._capability_request(plan, run, ())

    assert "endpoint_observation" in request.required_products
    assert request.metadata["knowledge_is_evidence"] is False
    assert request.metadata["knowledge_freshness_policy"] == "stale_records_excluded"
    assert request.metadata["knowledge_context"]["knowledge_matches"][0]["record_id"] == "fresh-next"
    assert not any(node.kind == "intelligence.finding" for node in run.graph.nodes.values())
