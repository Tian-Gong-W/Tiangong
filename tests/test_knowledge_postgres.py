from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from tonmen.knowledge import KnowledgeKind, KnowledgeRecord, KnowledgeStore


POSTGRES_URL = os.getenv("TONMEN_TEST_POSTGRES_URL", "").strip()
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="TONMEN_TEST_POSTGRES_URL is not configured")


def test_postgres_knowledge_store_round_trip(tmp_path) -> None:
    store = KnowledgeStore(tmp_path / "unused.db", database_url=POSTGRES_URL)
    now = datetime.now(timezone.utc)
    record = KnowledgeRecord.create(
        record_id="postgres-ci-record",
        kind=KnowledgeKind.PRODUCT_CHANGE,
        title="PostgreSQL integration record",
        summary="Exercises the shared production knowledge backend.",
        source="TONMEN CI",
        source_url="https://github.com/Top-Men-AI/Tiangong",
        published_at=now,
        retrieved_at=now,
        technologies=("postgres-ci-product",),
        tags=("postgres-ci",),
    )

    store.upsert(record)
    assert any(item.id == record.id for item in store.all())
    assert store.count() >= 1

    watch = {
        "target_key": "postgres-ci-target",
        "target": "postgres-ci.example",
        "product_names": ["postgres-ci-product"],
        "peer_entities": ["postgres-ci-peer"],
    }
    store.upsert_watch_target(watch["target_key"], watch)
    watches = store.watch_targets()
    assert any(item.get("target_key") == watch["target_key"] for item in watches)

    run_id = "postgres-ci-run"
    store.save_ingestion_run(run_id, {"id": run_id, "records_written": 1})

    comparison_id = "postgres-ci-comparison"
    store.save_peer_comparison(
        comparison_id,
        watch["target_key"],
        {"id": comparison_id, "target_key": watch["target_key"], "target": watch["target"]},
    )
    comparisons = store.latest_peer_comparisons(watch["target_key"])
    assert comparisons
    assert comparisons[0]["id"] == comparison_id
