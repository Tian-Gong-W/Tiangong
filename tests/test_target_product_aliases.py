from __future__ import annotations

from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun
from tonmen.reasoning import MissionDirector


def test_target_aware_finding_preserves_validation_product_alias():
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.graph.add_node(
        GraphNode(
            id="finding:demo",
            kind="intelligence.finding",
            label="Demo finding",
            metadata={
                "target": "https://localhost/demo",
                "evidence_id": "e-nuclei",
                "data": {"matched_at": "https://localhost/demo"},
            },
        )
    )

    products = MissionDirector._observed_products(run, "https://localhost")

    assert "finding" in products
    assert "validation_observation" in products


def test_target_aware_web_fact_preserves_http_and_technology_aliases():
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.graph.add_node(
        GraphNode(
            id="web:demo",
            kind="intelligence.web",
            label="HTTPS surface",
            metadata={
                "target": "localhost",
                "evidence_id": "e-httpx",
                "data": {"url": "https://localhost", "technologies": ["nginx"]},
            },
        )
    )

    products = MissionDirector._observed_products(run, "https://localhost")

    assert {"web_observation", "http_observation", "technology_observation"}.issubset(products)
