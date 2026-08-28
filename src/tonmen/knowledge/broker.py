from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from tonmen.missions import MissionRun

from .attack_path import AttackPathHypothesis, AttackPathSynthesizer
from .catalog import KnowledgeCatalog, KnowledgeMatch, KnowledgeQuery
from .profile import OrganizationScale, TargetProfile


def _dedupe(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item) for item in values if str(item)))


@dataclass(frozen=True, slots=True)
class KnowledgeContext:
    target_profile: TargetProfile
    matches: tuple[KnowledgeMatch, ...]
    attack_paths: tuple[AttackPathHypothesis, ...]
    required_products: tuple[str, ...]
    preferred_modalities: tuple[str, ...]
    rationale: str

    @property
    def active(self) -> bool:
        return bool(self.matches)

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_profile": self.target_profile.as_dict(),
            "knowledge_matches": [item.as_dict() for item in self.matches],
            "attack_paths": [item.as_dict() for item in self.attack_paths],
            "required_products": list(self.required_products),
            "preferred_modalities": list(self.preferred_modalities),
            "rationale": self.rationale,
        }


class KnowledgeBroker:
    """Freshness-first bridge between target evidence and capability requests."""

    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace)

    def context_for(
        self,
        run: MissionRun,
        *,
        metadata: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> KnowledgeContext:
        profile = TargetProfile.from_run(run, metadata=metadata)
        scales: list[str] = []
        if profile.organization_scale is not OrganizationScale.UNKNOWN:
            scales.append(profile.organization_scale.value)

        tags = ["general", f"surface:{profile.surface_scale.value}"]
        tags.extend(f"product:{item}" for item in profile.product_categories)

        query = KnowledgeQuery(
            technologies=profile.technologies,
            industries=profile.industries,
            organization_scales=tuple(scales),
            tags=tuple(tags),
            include_stale=False,
            limit=12,
        )
        matches = KnowledgeCatalog.from_workspace(self.workspace).query(query, now=now)
        attack_paths = AttackPathSynthesizer().synthesize(matches)

        required_products = _dedupe(
            [
                *(product for match in matches for product in match.record.required_products),
                *(product for path in attack_paths for product in path.required_products),
            ]
        )
        preferred_modalities = _dedupe(
            [
                *(modality for match in matches for modality in match.record.preferred_modalities),
                *(modality for path in attack_paths for modality in path.preferred_modalities),
            ]
        )

        if matches:
            rationale = (
                f"{len(matches)} fresh knowledge record(s) match the observed target profile"
                + (f"; {len(attack_paths)} chained attack-path hypothesis/hypotheses formed" if attack_paths else "")
                + ". Knowledge may prioritize evidence needs but cannot establish a Finding."
            )
        else:
            rationale = (
                "No fresh knowledge record currently matches the observed target profile; "
                "fall back to evidence-driven exploration without inventing modernity claims."
            )

        return KnowledgeContext(
            target_profile=profile,
            matches=matches,
            attack_paths=attack_paths,
            required_products=required_products,
            preferred_modalities=preferred_modalities,
            rationale=rationale,
        )
