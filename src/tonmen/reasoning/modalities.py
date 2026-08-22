from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .model import ActionProposal, Hypothesis, HypothesisStatus


@dataclass(frozen=True, slots=True)
class ModalityStep:
    """One step in the research modality ladder."""

    modality: str
    tool: str
    parameters: dict
    expected_info_gain: float
    risk: int
    requires_approval: bool
    rationale_template: str


# Ordered from cheapest / broadest observation toward deeper validation.
# Only tools that are already part of the governed TONMEN tool surface.
MODALITY_LADDER: tuple[ModalityStep, ...] = (
    ModalityStep(
        modality="network",
        tool="nmap",
        parameters={"args": ["-sV", "-T4", "--top-ports", "100"]},
        expected_info_gain=0.55,
        risk=1,
        requires_approval=False,
        rationale_template=(
            "Network modality: passive service discovery on {target} to expand the world model."
        ),
    ),
    ModalityStep(
        modality="web",
        tool="nuclei",
        parameters={"templates": ["http/technologies"], "severity": ["info", "low"]},
        expected_info_gain=0.50,
        risk=2,
        requires_approval=True,
        rationale_template=(
            "Web modality: technology / low-severity template check on {target} after a surface was observed."
        ),
    ),
)


def next_modality_proposals(
    *,
    target: str,
    tried: set[tuple[str, str]],
    has_web_surface: bool,
    fact_count: int,
) -> list[ActionProposal]:
    """Emit at most one next modality step that has not been tried yet."""
    proposals: list[ActionProposal] = []
    for step in MODALITY_LADDER:
        if (step.tool, target) in tried:
            continue
        # Gate web modality on evidence of a web surface, or very sparse facts
        if step.modality == "web" and not has_web_surface and fact_count >= 3:
            continue
        gain = step.expected_info_gain
        if fact_count == 0:
            gain = min(0.9, gain + 0.1)
        elif fact_count >= 5 and step.modality == "network":
            # Network already well covered → lower gain
            gain = max(0.2, gain - 0.25)
        if gain < 0.35:
            continue
        proposals.append(
            ActionProposal.create(
                tool=step.tool,
                target=target,
                parameters=dict(step.parameters),
                rationale=step.rationale_template.format(target=target),
                expected_info_gain=gain,
                risk=step.risk,
                requires_approval=step.requires_approval,
                estimated_cost=1,
                metadata={"modality": step.modality, "phase": 3},
            )
        )
        break  # one modality switch at a time
    return proposals


def discriminating_experiment(
    *,
    target: str,
    open_hypotheses: Iterable[Hypothesis],
    tried: set[tuple[str, str]],
) -> tuple[list[Hypothesis], list[ActionProposal]]:
    """When two or more open hypotheses compete, propose the cheapest experiment
    that can separate them — not another blind scan.
    """
    open_list = [h for h in open_hypotheses if h.status is HypothesisStatus.OPEN and h.confidence >= 0.25]
    if len(open_list) < 2:
        return [], []

    # Prefer a low-risk network probe if not yet done; otherwise a gated web check.
    if ("nmap", target) not in tried:
        meta_hypo = Hypothesis.create(
            statement=(
                f"Competing hypotheses on {target} can be separated by a cheap network fingerprint."
            ),
            confidence=0.45,
            status=HypothesisStatus.OPEN,
            metadata={"kind": "discriminating", "competitor_ids": [h.id for h in open_list[:4]]},
        )
        proposal = ActionProposal.create(
            tool="nmap",
            target=target,
            parameters={"args": ["-sV", "-T4", "-p", "80,443,8080,8443"]},
            rationale=(
                "Discriminating experiment: narrow service probe to test which open hypothesis "
                "about exposed surfaces remains viable."
            ),
            expected_info_gain=0.60,
            risk=1,
            requires_approval=False,
            hypothesis_id=meta_hypo.id,
            estimated_cost=1,
            metadata={"kind": "discriminating_experiment", "phase": 3},
        )
        return [meta_hypo], [proposal]

    if ("nuclei", target) not in tried:
        meta_hypo = Hypothesis.create(
            statement=(
                f"Competing hypotheses on {target} may be separated by a constrained web technology check."
            ),
            confidence=0.4,
            status=HypothesisStatus.OPEN,
            metadata={"kind": "discriminating", "competitor_ids": [h.id for h in open_list[:4]]},
        )
        proposal = ActionProposal.create(
            tool="nuclei",
            target=target,
            parameters={"templates": ["http/technologies"], "severity": ["info"]},
            rationale=(
                "Discriminating experiment: constrained technology templates to resolve "
                "which competing web-surface hypothesis is still consistent with evidence."
            ),
            expected_info_gain=0.55,
            risk=2,
            requires_approval=True,
            hypothesis_id=meta_hypo.id,
            estimated_cost=1,
            metadata={"kind": "discriminating_experiment", "phase": 3},
        )
        return [meta_hypo], [proposal]

    return [], []
