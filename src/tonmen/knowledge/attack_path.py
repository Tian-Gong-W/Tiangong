from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .catalog import KnowledgeMatch
from .model import KnowledgeKind


@dataclass(frozen=True, slots=True)
class AttackPathHypothesis:
    """Non-executing chained hypothesis over knowledge records.

    It describes possible state transitions and evidence needs only. Execution
    remains the responsibility of the governed Capability plane.
    """

    id: str
    knowledge_ids: tuple[str, ...]
    titles: tuple[str, ...]
    state_changes: tuple[str, ...]
    required_products: tuple[str, ...]
    preferred_modalities: tuple[str, ...]
    confidence: float

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "knowledge_ids": list(self.knowledge_ids),
            "titles": list(self.titles),
            "state_changes": list(self.state_changes),
            "required_products": list(self.required_products),
            "preferred_modalities": list(self.preferred_modalities),
            "confidence": round(self.confidence, 4),
        }


def _dedupe(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item) for item in values if str(item)))


class AttackPathSynthesizer:
    def __init__(self, *, max_depth: int = 4, limit: int = 6) -> None:
        self.max_depth = max(2, int(max_depth))
        self.limit = max(1, int(limit))

    @staticmethod
    def _key(match: KnowledgeMatch) -> str:
        return str(match.record.technique_id or match.record.id).strip().casefold()

    def synthesize(self, matches: tuple[KnowledgeMatch, ...]) -> tuple[AttackPathHypothesis, ...]:
        candidates = tuple(
            match
            for match in matches
            if match.record.kind in {KnowledgeKind.TECHNIQUE, KnowledgeKind.THREAT_PATTERN}
        )
        by_key = {self._key(match): match for match in candidates}
        paths: list[AttackPathHypothesis] = []
        seen: set[tuple[str, ...]] = set()

        def walk(chain: tuple[KnowledgeMatch, ...]) -> None:
            if len(paths) >= self.limit or len(chain) >= self.max_depth:
                return
            tail = chain[-1]
            for enabled in tail.record.enables:
                nxt = by_key.get(str(enabled).strip().casefold())
                if nxt is None or nxt in chain:
                    continue
                extended = (*chain, nxt)
                key = tuple(item.record.id for item in extended)
                if key not in seen:
                    seen.add(key)
                    paths.append(
                        AttackPathHypothesis(
                            id=uuid4().hex,
                            knowledge_ids=key,
                            titles=tuple(item.record.title for item in extended),
                            state_changes=_dedupe(
                                change
                                for item in extended
                                for change in item.record.state_changes
                            ),
                            required_products=_dedupe(
                                product
                                for item in extended
                                for product in item.record.required_products
                            ),
                            preferred_modalities=_dedupe(
                                modality
                                for item in extended
                                for modality in item.record.preferred_modalities
                            ),
                            confidence=min(item.effective_weight for item in extended),
                        )
                    )
                walk(extended)

        for match in candidates:
            if match.record.enables:
                walk((match,))
            if len(paths) >= self.limit:
                break

        paths.sort(key=lambda item: (len(item.knowledge_ids), item.confidence), reverse=True)
        return tuple(paths[: self.limit])
