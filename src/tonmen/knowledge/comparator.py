from __future__ import annotations

import hashlib
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .model import KnowledgeRecord


def _terms(values: Iterable[Any]) -> tuple[str, ...]:
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


def _haystack(record: KnowledgeRecord) -> str:
    metadata = record.metadata
    pieces = [
        record.title,
        record.summary,
        *record.technologies,
        *record.industries,
        *record.tags,
        str(metadata.get("vendor") or ""),
        str(metadata.get("product") or ""),
        str(metadata.get("entity") or ""),
        str(metadata.get("product_category") or ""),
    ]
    return " ".join(piece.casefold() for piece in pieces if piece)


def _matches(record: KnowledgeRecord, terms: Iterable[str]) -> bool:
    text = _haystack(record)
    return any(term.casefold() in text for term in terms if term)


def _severity(record: KnowledgeRecord) -> str:
    value = str(record.metadata.get("severity") or "").strip().lower()
    if value:
        return value
    for tag in record.tags:
        if str(tag).lower().startswith("severity:"):
            return str(tag).split(":", 1)[1].strip().lower()
    return "unknown"


def _metrics(records: Iterable[KnowledgeRecord], *, now: datetime) -> dict[str, Any]:
    rows = tuple(records)
    by_kind: dict[str, int] = {}
    high_critical = 0
    known_exploited = 0
    fresh_weight = 0.0
    for record in rows:
        by_kind[record.kind.value] = by_kind.get(record.kind.value, 0) + 1
        if _severity(record) in {"high", "critical"}:
            high_critical += 1
        if "known-exploited" in {tag.casefold() for tag in record.tags}:
            known_exploited += 1
        fresh_weight += record.effective_weight(now=now)
    return {
        "record_count": len(rows),
        "by_kind": dict(sorted(by_kind.items())),
        "high_critical_count": high_critical,
        "known_exploited_count": known_exploited,
        "freshness_weighted_signal": round(fresh_weight, 4),
    }


@dataclass(frozen=True, slots=True)
class MarketComparison:
    id: str
    target_key: str
    target: str
    generated_at: datetime
    target_signal: Mapping[str, Any]
    peers: tuple[Mapping[str, Any], ...]
    category_baseline: Mapping[str, Any]
    caveat: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_key": self.target_key,
            "target": self.target,
            "generated_at": self.generated_at.isoformat(),
            "target_signal": dict(self.target_signal),
            "peers": [dict(item) for item in self.peers],
            "category_baseline": dict(self.category_baseline),
            "caveat": self.caveat,
        }


class MarketComparator:
    """Compare public knowledge activity without pretending it is a security score.

    The output measures how much fresh public security/product knowledge references
    a target or peer. It must not be interpreted as breach probability, security
    maturity, or a proof that one company is safer than another.
    """

    CAVEAT = (
        "This comparison reflects fresh public knowledge activity and observed product/security signals only. "
        "It is not a security maturity rating, breach probability, or evidence that one organization is safer."
    )

    @staticmethod
    def _target_terms(watch: Mapping[str, Any]) -> tuple[str, ...]:
        return _terms(
            [
                *(watch.get("product_names") or ()),
                *(watch.get("technologies") or ()),
                *(watch.get("entity_names") or ()),
            ]
        )

    @staticmethod
    def _category_terms(watch: Mapping[str, Any]) -> tuple[str, ...]:
        return _terms(
            [
                *(watch.get("product_categories") or ()),
                *(watch.get("industries") or ()),
            ]
        )

    def compare(
        self,
        watch: Mapping[str, Any],
        records: Iterable[KnowledgeRecord],
        *,
        now: datetime | None = None,
    ) -> MarketComparison:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        rows = tuple(record for record in records if record.effective_weight(now=current) > 0.0)
        target_terms = self._target_terms(watch)
        category_terms = self._category_terms(watch)
        peer_names = _terms(watch.get("peer_entities") or ())

        target_records = tuple(record for record in rows if _matches(record, target_terms)) if target_terms else ()
        peer_rows: list[dict[str, Any]] = []
        peer_weights: list[float] = []
        for peer in peer_names:
            matched = tuple(record for record in rows if _matches(record, (peer,)))
            metrics = _metrics(matched, now=current)
            metrics["entity"] = peer
            peer_weights.append(float(metrics["freshness_weighted_signal"]))
            peer_rows.append(metrics)

        category_records = tuple(record for record in rows if _matches(record, category_terms)) if category_terms else ()
        baseline = _metrics(category_records, now=current)
        baseline["category_terms"] = list(category_terms)
        if peer_weights:
            baseline["peer_median_freshness_weighted_signal"] = round(statistics.median(peer_weights), 4)
        else:
            baseline["peer_median_freshness_weighted_signal"] = None

        target_key = str(watch.get("target_key") or "").strip()
        target = str(watch.get("target") or "").strip()
        comparison_id = hashlib.sha256(
            f"{target_key}\0{current.date().isoformat()}".encode("utf-8")
        ).hexdigest()[:32]
        return MarketComparison(
            id=comparison_id,
            target_key=target_key,
            target=target,
            generated_at=current,
            target_signal=_metrics(target_records, now=current),
            peers=tuple(peer_rows),
            category_baseline=baseline,
            caveat=self.CAVEAT,
        )
