from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

from .comparator import MarketComparator
from .feeds import FeedSpec, cisa_kev_records, nvd_recent_records, rss_atom_records
from .model import KnowledgeRecord, utcnow
from .store import KnowledgeStore


def _unique(values: Iterable[Any]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return tuple(result)


def _record_text(record: KnowledgeRecord) -> str:
    metadata = record.metadata
    pieces = [
        record.title,
        record.summary,
        *record.technologies,
        *record.industries,
        *record.organization_scales,
        *record.tags,
        str(metadata.get("vendor") or ""),
        str(metadata.get("product") or ""),
        str(metadata.get("entity") or ""),
        str(metadata.get("product_category") or ""),
    ]
    return " ".join(str(piece).casefold() for piece in pieces if str(piece).strip())


@dataclass(frozen=True, slots=True)
class InterestProfile:
    target_terms: tuple[str, ...]
    peer_terms: tuple[str, ...]
    category_terms: tuple[str, ...]

    @property
    def active(self) -> bool:
        return bool(self.target_terms or self.peer_terms or self.category_terms)

    @classmethod
    def from_watches(cls, watches: Iterable[Mapping[str, Any]]) -> "InterestProfile":
        target_terms: list[str] = []
        peer_terms: list[str] = []
        category_terms: list[str] = []
        for watch in watches:
            target_terms.extend(watch.get("product_names") or ())
            target_terms.extend(watch.get("technologies") or ())
            target_terms.extend(watch.get("entity_names") or ())
            peer_terms.extend(watch.get("peer_entities") or ())
            category_terms.extend(watch.get("product_categories") or ())
            category_terms.extend(watch.get("industries") or ())
        return cls(
            target_terms=_unique(target_terms),
            peer_terms=_unique(peer_terms),
            category_terms=_unique(category_terms),
        )

    def classify(self, record: KnowledgeRecord) -> tuple[float, tuple[str, ...]]:
        text = _record_text(record)
        reasons: list[str] = []
        score = 0.0
        for term in self.target_terms:
            if term.casefold() in text:
                score += 4.0
                reasons.append(f"target:{term}")
        for term in self.peer_terms:
            if term.casefold() in text:
                score += 2.0
                reasons.append(f"peer:{term}")
        for term in self.category_terms:
            if term.casefold() in text:
                score += 1.0
                reasons.append(f"category:{term}")
        tags = {str(tag).casefold() for tag in record.tags}
        severity = str(record.metadata.get("severity") or "").strip().lower()
        if "known-exploited" in tags:
            score += 3.0
            reasons.append("known-exploited")
        if severity == "critical":
            score += 1.5
            reasons.append("severity:critical")
        elif severity == "high":
            score += 0.75
            reasons.append("severity:high")
        score += record.effective_weight() * 0.25
        return score, tuple(dict.fromkeys(reasons))


@dataclass(frozen=True, slots=True)
class CrawlResult:
    run_id: str
    started_at: datetime
    finished_at: datetime
    source_stats: Mapping[str, Mapping[str, Any]]
    records_seen: int
    records_selected: int
    records_written: int
    watch_targets: int
    peer_comparisons: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "source_stats": {key: dict(value) for key, value in self.source_stats.items()},
            "records_seen": self.records_seen,
            "records_selected": self.records_selected,
            "records_written": self.records_written,
            "watch_targets": self.watch_targets,
            "peer_comparisons": self.peer_comparisons,
        }


class KnowledgeCrawler:
    """Daily target-first public knowledge ingestion pipeline.

    The crawler may collect public security/product knowledge and produce market
    comparison signals. It never converts knowledge into target Findings and never
    expands mission Scope or approval authority.
    """

    def __init__(self, store: KnowledgeStore, *, now: datetime | None = None) -> None:
        self.store = store
        self.now = (now or utcnow()).astimezone(timezone.utc)

    @staticmethod
    def _env_json(name: str, default):
        raw = str(os.getenv(name) or "").strip()
        if not raw:
            return default
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{name} must contain valid JSON") from exc
        return value

    def _seed_env_watches(self) -> None:
        value = self._env_json("TONMEN_KNOWLEDGE_TARGETS_JSON", [])
        if not isinstance(value, list):
            raise ValueError("TONMEN_KNOWLEDGE_TARGETS_JSON must be a JSON array")
        for index, item in enumerate(value):
            if not isinstance(item, Mapping):
                continue
            target = str(item.get("target") or item.get("name") or "").strip()
            if not target:
                continue
            target_key = str(item.get("target_key") or f"env:{index}:{target.casefold()}")
            payload = dict(item)
            payload["target"] = target
            payload["source"] = "environment"
            self.store.upsert_watch_target(target_key, payload)

    def _feed_specs(self, watches: Iterable[Mapping[str, Any]]) -> tuple[FeedSpec, ...]:
        raw_specs = self._env_json("TONMEN_KNOWLEDGE_FEEDS_JSON", [])
        if not isinstance(raw_specs, list):
            raise ValueError("TONMEN_KNOWLEDGE_FEEDS_JSON must be a JSON array")
        values: list[Mapping[str, Any]] = [item for item in raw_specs if isinstance(item, Mapping)]
        for watch in watches:
            sources = watch.get("knowledge_sources")
            if isinstance(sources, list):
                values.extend(item for item in sources if isinstance(item, Mapping))
        specs: list[FeedSpec] = []
        seen: set[str] = set()
        for value in values:
            try:
                spec = FeedSpec.from_dict(value)
            except (TypeError, ValueError):
                continue
            key = spec.url.casefold()
            if key in seen:
                continue
            seen.add(key)
            specs.append(spec)
        return tuple(specs)

    @staticmethod
    def _annotate(record: KnowledgeRecord, *, score: float, reasons: tuple[str, ...], run_id: str) -> KnowledgeRecord:
        data = record.as_dict()
        metadata = dict(data.get("metadata") or {})
        metadata.update(
            {
                "priority_score": round(float(score), 4),
                "priority_reasons": list(reasons),
                "ingestion_run_id": run_id,
                "ingestion_mode": "daily-target-first",
            }
        )
        data["metadata"] = metadata
        return KnowledgeRecord.from_dict(data)

    def _select(
        self,
        records: Iterable[KnowledgeRecord],
        interest: InterestProfile,
        *,
        run_id: str,
        explicit_source: bool,
    ) -> tuple[KnowledgeRecord, ...]:
        ranked: list[tuple[float, KnowledgeRecord]] = []
        for record in records:
            score, reasons = interest.classify(record)
            tags = {str(tag).casefold() for tag in record.tags}
            severity = str(record.metadata.get("severity") or "").strip().lower()
            keep = explicit_source or "known-exploited" in tags or severity in {"high", "critical"}
            if interest.active and reasons:
                keep = True
            if not keep:
                continue
            ranked.append((score, self._annotate(record, score=score, reasons=reasons, run_id=run_id)))
        ranked.sort(key=lambda item: (item[0], item[1].published_at), reverse=True)
        max_records = max(50, int(os.getenv("TONMEN_KNOWLEDGE_MAX_RECORDS_PER_RUN", "1000")))
        return tuple(record for _, record in ranked[:max_records])

    def run(self) -> CrawlResult:
        started = self.now
        run_id = uuid4().hex
        self._seed_env_watches()
        watches = self.store.watch_targets()
        interest = InterestProfile.from_watches(watches)
        source_stats: dict[str, dict[str, Any]] = {}
        selected: dict[str, KnowledgeRecord] = {}
        seen_count = 0

        def collect(name: str, loader, *, explicit_source: bool = False) -> None:
            nonlocal seen_count
            try:
                records = tuple(loader())
                seen_count += len(records)
                chosen = self._select(records, interest, run_id=run_id, explicit_source=explicit_source)
                for record in chosen:
                    selected[record.id] = record
                source_stats[name] = {
                    "status": "ok",
                    "seen": len(records),
                    "selected": len(chosen),
                }
            except Exception as exc:
                source_stats[name] = {
                    "status": "error",
                    "seen": 0,
                    "selected": 0,
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                }

        collect("cisa-kev", lambda: cisa_kev_records(now=self.now))
        collect(
            "nvd-recent",
            lambda: nvd_recent_records(
                now=self.now,
                lookback_hours=int(os.getenv("TONMEN_NVD_LOOKBACK_HOURS", "36")),
                max_pages=int(os.getenv("TONMEN_NVD_MAX_PAGES", "3")),
            ),
        )
        for spec in self._feed_specs(watches):
            collect(f"feed:{spec.name}", lambda spec=spec: rss_atom_records(spec, now=self.now), explicit_source=True)

        written = tuple(selected.values())
        self.store.upsert_many(written)

        all_records = self.store.all()
        comparator = MarketComparator()
        comparison_count = 0
        for watch in watches:
            target_key = str(watch.get("target_key") or "").strip()
            if not target_key:
                continue
            comparison = comparator.compare(watch, all_records, now=self.now)
            self.store.save_peer_comparison(comparison.id, target_key, comparison.as_dict())
            comparison_count += 1

        finished = utcnow().astimezone(timezone.utc)
        result = CrawlResult(
            run_id=run_id,
            started_at=started,
            finished_at=finished,
            source_stats=source_stats,
            records_seen=seen_count,
            records_selected=len(selected),
            records_written=len(written),
            watch_targets=len(watches),
            peer_comparisons=comparison_count,
        )
        self.store.save_ingestion_run(run_id, result.as_dict())
        return result


def run_for_workspace(workspace: Path | str) -> CrawlResult:
    return KnowledgeCrawler(KnowledgeStore.for_workspace(workspace)).run()
