from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .model import FreshnessState, KnowledgeRecord
from .store import KnowledgeStore


def _keys(values) -> set[str]:
    return {str(item).strip().casefold() for item in values or () if str(item).strip()}


@dataclass(frozen=True, slots=True)
class KnowledgeQuery:
    technologies: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    organization_scales: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    include_stale: bool = False
    limit: int = 12


@dataclass(frozen=True, slots=True)
class KnowledgeMatch:
    record: KnowledgeRecord
    match_score: float
    effective_weight: float
    freshness_state: FreshnessState

    @property
    def score(self) -> float:
        return self.match_score * self.effective_weight

    def as_dict(self) -> dict:
        return {
            "record_id": self.record.id,
            "kind": self.record.kind.value,
            "title": self.record.title,
            "source": self.record.source,
            "published_at": self.record.published_at.isoformat(),
            "freshness": self.freshness_state.value,
            "match_score": round(self.match_score, 4),
            "effective_weight": round(self.effective_weight, 4),
            "score": round(self.score, 4),
        }


class KnowledgeCatalog:
    def __init__(self, records=()) -> None:
        self.records = tuple(records)

    @classmethod
    def from_workspace(cls, workspace: Path | str) -> "KnowledgeCatalog":
        records = list(KnowledgeStore.for_workspace(workspace).all())
        seed_path = str(os.getenv("TONMEN_KNOWLEDGE_PATH") or "").strip()
        if seed_path:
            records.extend(cls._read_jsonl(Path(seed_path)))
        by_id = {record.id: record for record in records}
        return cls(by_id.values())

    @staticmethod
    def _read_jsonl(path: Path) -> tuple[KnowledgeRecord, ...]:
        if not path.exists() or not path.is_file():
            return ()
        records: list[KnowledgeRecord] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ()
        for line in lines:
            text = line.strip()
            if not text:
                continue
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    records.append(KnowledgeRecord.from_dict(data))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return tuple(records)

    @staticmethod
    def _dimension_score(query_values, record_values, weight: float) -> tuple[float, bool]:
        query_keys = _keys(query_values)
        record_keys = _keys(record_values)
        if not query_keys or not record_keys:
            return 0.0, False
        overlap = query_keys.intersection(record_keys)
        if not overlap:
            return 0.0, False
        return weight * (len(overlap) / max(1, len(query_keys))), True

    def query(self, query: KnowledgeQuery, *, now: datetime | None = None) -> tuple[KnowledgeMatch, ...]:
        matches: list[KnowledgeMatch] = []
        for record in self.records:
            freshness = record.freshness_state(now=now)
            if freshness is FreshnessState.STALE and not query.include_stale:
                continue

            score = 0.0
            matched = False
            for query_values, record_values, weight in (
                (query.technologies, record.technologies, 0.55),
                (query.industries, record.industries, 0.20),
                (query.organization_scales, record.organization_scales, 0.15),
                (query.tags, record.tags, 0.10),
            ):
                contribution, dimension_matched = self._dimension_score(query_values, record_values, weight)
                score += contribution
                matched = matched or dimension_matched

            # Generic current records must opt in via the "general" tag; otherwise a
            # knowledge item for an unrelated stack cannot influence the mission.
            if not matched and "general" in _keys(record.tags) and "general" in _keys(query.tags):
                score = 0.10
                matched = True
            if not matched:
                continue

            effective = record.effective_weight(now=now)
            if effective <= 0.0 and not query.include_stale:
                continue
            matches.append(
                KnowledgeMatch(
                    record=record,
                    match_score=max(0.0, min(1.0, score)),
                    effective_weight=effective,
                    freshness_state=freshness,
                )
            )

        matches.sort(key=lambda item: (item.score, item.record.published_at), reverse=True)
        return tuple(matches[: max(1, int(query.limit))])
