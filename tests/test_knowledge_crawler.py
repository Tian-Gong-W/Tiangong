from __future__ import annotations

from datetime import datetime, timezone

from tonmen.knowledge import KnowledgeKind, KnowledgeRecord, KnowledgeStore, MarketComparator, stable_record_id
from tonmen.knowledge.crawler import KnowledgeCrawler

_NOW = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)


def _record(
    record_id: str,
    *,
    technology: str,
    severity: str = "low",
    tags=(),
    source: str = "test",
) -> KnowledgeRecord:
    return KnowledgeRecord.create(
        record_id=record_id,
        kind=KnowledgeKind.THREAT_PATTERN,
        title=f"{technology} advisory",
        summary=f"Fresh public security knowledge for {technology}",
        source=source,
        source_url="https://example.com/advisory",
        published_at=_NOW,
        retrieved_at=_NOW,
        technologies=(technology,),
        tags=tuple(tags),
        metadata={"severity": severity},
    )


def test_stable_feed_record_id_deduplicates_by_source_and_external_id():
    assert stable_record_id("NVD", "CVE-2026-1234") == stable_record_id("nvd", "cve-2026-1234")
    assert stable_record_id("NVD", "CVE-2026-1234") != stable_record_id("CISA KEV", "CVE-2026-1234")


def test_store_persists_watch_targets_and_peer_snapshots(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    store.upsert_watch_target(
        "target-1",
        {
            "target": "example.test",
            "product_names": ["Acme Portal"],
            "peer_entities": ["PeerCo"],
        },
    )
    watches = store.watch_targets()
    assert len(watches) == 1
    assert watches[0]["product_names"] == ["Acme Portal"]

    store.save_peer_comparison("comparison-1", "target-1", {"target": "example.test", "signal": 2})
    snapshots = store.latest_peer_comparisons("target-1")
    assert snapshots[0]["signal"] == 2


def test_daily_crawler_prioritizes_target_products_and_keeps_kev(tmp_path, monkeypatch):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    store.upsert_watch_target(
        "target-1",
        {
            "target_key": "target-1",
            "target": "example.test",
            "product_names": ["Acme Portal"],
            "peer_entities": ["PeerCo"],
            "product_categories": ["identity"],
        },
    )
    target_record = _record("target", technology="Acme Portal", severity="low")
    unrelated_low = _record("unrelated", technology="Other Product", severity="low")
    peer_high = _record("peer", technology="PeerCo", severity="high")
    kev = _record("kev", technology="Legacy Appliance", severity="medium", tags=("known-exploited",))

    monkeypatch.setattr("tonmen.knowledge.crawler.cisa_kev_records", lambda now=None: (kev,))
    monkeypatch.setattr(
        "tonmen.knowledge.crawler.nvd_recent_records",
        lambda **kwargs: (target_record, unrelated_low, peer_high),
    )

    result = KnowledgeCrawler(store, now=_NOW).run()
    stored = {record.id: record for record in store.all()}

    assert result.records_seen == 4
    assert {"target", "peer", "kev"}.issubset(stored)
    assert "unrelated" not in stored
    assert any(reason.startswith("target:Acme Portal") for reason in stored["target"].metadata["priority_reasons"])
    assert any(reason.startswith("peer:PeerCo") for reason in stored["peer"].metadata["priority_reasons"])
    assert result.peer_comparisons == 1


def test_market_comparison_is_activity_signal_not_security_rating():
    watch = {
        "target_key": "target-1",
        "target": "example.test",
        "product_names": ["Acme Portal"],
        "peer_entities": ["PeerCo"],
        "product_categories": ["identity"],
    }
    target = _record("target", technology="Acme Portal", severity="critical", tags=("known-exploited",))
    peer = _record("peer", technology="PeerCo", severity="high")

    comparison = MarketComparator().compare(watch, (target, peer), now=_NOW)

    assert comparison.target_signal["record_count"] == 1
    assert comparison.peers[0]["record_count"] == 1
    assert "not a security maturity rating" in comparison.caveat
