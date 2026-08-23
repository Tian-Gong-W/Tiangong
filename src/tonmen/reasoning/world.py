from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tonmen.missions import ActionOutcome, ActionOutcomeKind, MissionRun, StepExecutionState

from .model import Hypothesis, HypothesisStatus


@dataclass(frozen=True, slots=True)
class EvidenceNeed:
    hypothesis_id: str
    description: str
    required_products: tuple[str, ...] = ()
    preferred_modalities: tuple[str, ...] = ()
    missing_products: tuple[str, ...] = ()

    @property
    def explicit(self) -> bool:
        return bool(self.required_products or self.preferred_modalities)


@dataclass(frozen=True, slots=True)
class WorldModel:
    """Evidence-derived research state consumed by the Mission Director.

    The graph remains the durable provenance store. WorldModel is a deterministic
    projection over that graph plus the ActionLedger-compatible execution history,
    so it can always be rebuilt after restart instead of becoming a second source
    of truth.
    """

    target: str
    fact_ids: tuple[str, ...]
    fact_kinds: tuple[str, ...]
    hypotheses: tuple[Hypothesis, ...]
    evidence_needs: tuple[EvidenceNeed, ...]
    observed_products: tuple[str, ...]
    observed_modalities: tuple[str, ...]
    action_outcomes: tuple[ActionOutcome, ...]
    attempted_actions: tuple[tuple[str, str], ...]
    unavailable_capabilities: tuple[str, ...]
    denied_actions: tuple[tuple[str, str], ...]
    contradiction_fact_ids: tuple[str, ...]

    @property
    def open_hypotheses(self) -> tuple[Hypothesis, ...]:
        return tuple(item for item in self.hypotheses if item.status is HypothesisStatus.OPEN)

    @property
    def supported_hypotheses(self) -> tuple[Hypothesis, ...]:
        return tuple(item for item in self.hypotheses if item.status is HypothesisStatus.SUPPORTED)

    @property
    def environmental_outcomes(self) -> tuple[ActionOutcome, ...]:
        return tuple(item for item in self.action_outcomes if item.environmental)

    def was_attempted(self, tool: str, target: str) -> bool:
        key = (str(tool).strip().lower(), str(target))
        return key in set(self.attempted_actions)

    def is_capability_blocked(self, tool: str, target: str) -> bool:
        normalized = str(tool).strip().lower()
        return normalized in set(self.unavailable_capabilities) or (normalized, str(target)) in set(self.denied_actions)

    def missing_products(self) -> tuple[str, ...]:
        missing: list[str] = []
        for need in self.evidence_needs:
            for product in need.missing_products:
                if product not in missing:
                    missing.append(product)
        return tuple(missing)

    @classmethod
    def from_run(cls, run: MissionRun, *, registry: Any | None = None) -> "WorldModel":
        fact_nodes = sorted(
            (node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")),
            key=lambda node: node.id,
        )
        fact_ids = tuple(node.id for node in fact_nodes)
        fact_kinds = tuple(dict.fromkeys(node.kind.removeprefix("intelligence.") for node in fact_nodes))

        observed_products: list[str] = []
        for kind in fact_kinds:
            product = "finding" if kind == "finding" else f"{kind}_observation"
            if product not in observed_products:
                observed_products.append(product)

        hypotheses: list[Hypothesis] = []
        contradiction_fact_ids: list[str] = []
        for node in run.graph.nodes.values():
            if node.kind != "hypothesis":
                continue
            metadata = dict(node.metadata)
            raw_status = str(metadata.get("status") or HypothesisStatus.OPEN.value).lower()
            try:
                status = HypothesisStatus(raw_status)
            except ValueError:
                status = HypothesisStatus.OPEN
            contradicting = tuple(str(item) for item in metadata.get("contradicting_fact_ids", ()))
            for fact_id in contradicting:
                if fact_id not in contradiction_fact_ids:
                    contradiction_fact_ids.append(fact_id)
            hypotheses.append(
                Hypothesis(
                    id=node.id,
                    statement=node.label,
                    confidence=float(metadata.get("confidence") or 0.5),
                    supporting_fact_ids=tuple(str(item) for item in metadata.get("supporting_fact_ids", ())),
                    contradicting_fact_ids=contradicting,
                    status=status,
                    metadata=metadata,
                )
            )

        observed_modalities: list[str] = []
        if registry is not None:
            for execution in run.steps:
                if execution.state not in {StepExecutionState.SUCCEEDED, StepExecutionState.DEGRADED}:
                    continue
                try:
                    spec = registry.get(execution.tool).spec
                except KeyError:
                    continue
                for modality in spec.modalities:
                    if modality not in observed_modalities:
                        observed_modalities.append(modality)

        outcomes: list[ActionOutcome] = []
        for node in run.graph.nodes.values():
            if node.kind != "action.outcome":
                continue
            try:
                outcomes.append(ActionOutcome.from_graph_node(node))
            except (KeyError, ValueError, TypeError):
                continue

        attempted: list[tuple[str, str]] = []
        for execution in run.steps:
            if execution.state is StepExecutionState.PENDING:
                continue
            key = (execution.tool.strip().lower(), execution.target)
            if key not in attempted:
                attempted.append(key)

        unavailable: list[str] = []
        denied: list[tuple[str, str]] = []
        for outcome in outcomes:
            tool = outcome.tool.strip().lower()
            if outcome.kind is ActionOutcomeKind.TOOL_UNAVAILABLE and tool and tool not in unavailable:
                unavailable.append(tool)
            if outcome.kind in {ActionOutcomeKind.POLICY_DENIED, ActionOutcomeKind.OUT_OF_SCOPE}:
                key = (tool, outcome.target)
                if key not in denied:
                    denied.append(key)

        observed_set = set(observed_products)
        needs: list[EvidenceNeed] = []
        for hypothesis in hypotheses:
            if hypothesis.status is not HypothesisStatus.OPEN:
                continue
            metadata = dict(hypothesis.metadata)
            required = tuple(str(item) for item in metadata.get("required_products", ()) if str(item))
            modalities = tuple(str(item) for item in metadata.get("preferred_modalities", ()) if str(item))
            missing = tuple(item for item in required if item not in observed_set)
            description = str(metadata.get("evidence_need") or f"Resolve hypothesis: {hypothesis.statement}")
            needs.append(
                EvidenceNeed(
                    hypothesis_id=hypothesis.id,
                    description=description,
                    required_products=required,
                    preferred_modalities=modalities,
                    missing_products=missing,
                )
            )

        return cls(
            target=run.target,
            fact_ids=fact_ids,
            fact_kinds=fact_kinds,
            hypotheses=tuple(hypotheses),
            evidence_needs=tuple(needs),
            observed_products=tuple(observed_products),
            observed_modalities=tuple(observed_modalities),
            action_outcomes=tuple(outcomes),
            attempted_actions=tuple(attempted),
            unavailable_capabilities=tuple(unavailable),
            denied_actions=tuple(denied),
            contradiction_fact_ids=tuple(contradiction_fact_ids),
        )
