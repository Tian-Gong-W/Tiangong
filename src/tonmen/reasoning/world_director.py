from __future__ import annotations

from dataclasses import dataclass, replace

from tonmen.missions import MissionPlan, MissionRun, StepExecutionState, iter_plan_executions
from tonmen.tools import CapabilityRequest, CapabilityResolution, RiskLevel
from tonmen.tools.resolver import CapabilityResolver

from .director import MissionDirector as _LegacyCapabilityDirector
from .director import _CapabilityCandidate, _TARGET_CANDIDATE_LIMIT
from .model import Hypothesis, HypothesisStatus, ReasoningAction, ReasoningDecision
from .world import WorldModel


@dataclass(frozen=True, slots=True)
class _RequestedCandidate(_CapabilityCandidate):
    request: CapabilityRequest
    resolution: CapabilityResolution


class MissionDirector(_LegacyCapabilityDirector):
    """WorldModel Director that asks for evidence before selecting an adapter.

    The Director forms a tool-independent CapabilityRequest from current evidence
    needs. CapabilityResolver performs late binding against the current Registry,
    Policy and learned capability envelope. Concrete tool identity is therefore a
    resolution result, not the research question itself.
    """

    @staticmethod
    def _world(run: MissionRun, registry=None) -> WorldModel:
        return WorldModel.from_run(run, registry=registry)

    @staticmethod
    def _initial_hypothesis(run: MissionRun) -> Hypothesis | None:
        if any(node.kind == "hypothesis" for node in run.graph.nodes.values()):
            return None
        return Hypothesis.create(
            statement=(
                f"Authorized target {run.target} may expose observable network or web behavior "
                "that can be characterized by evidence."
            ),
            confidence=0.5,
            status=HypothesisStatus.OPEN,
            metadata={
                "kind": "bootstrap",
                "source": "mission_director",
                "evidence_need": "characterize the observable target surface",
                "required_products": ["service_observation", "http_observation"],
                "preferred_modalities": ["network", "http"],
            },
        )

    @classmethod
    def _attempted_actions(cls, plan: MissionPlan, run: MissionRun) -> set[tuple[str, str]]:
        return set(cls._world(run).attempted_actions)

    def _observed_modalities(self, plan: MissionPlan, run: MissionRun) -> set[str]:
        registry = self.runtime.registry if self.runtime is not None else None
        return set(self._world(run, registry).observed_modalities)

    @classmethod
    def _candidate_targets(cls, plan: MissionPlan, run: MissionRun, spec):
        """Prefer an existing governed compatibility target before late binding.

        Frozen plan order never becomes execution authority. But when the plan
        already contains a pending slot for the same capability, its exact target
        should be considered before inventing a semantically redundant dynamic
        action. Evidence-derived origins and ports remain available afterwards, so
        genuinely distinct surfaces can still be explored independently.
        """
        capabilities = set(spec.capabilities)
        if "domain.enumerate" in capabilities or "subdomain.discover" in capabilities:
            return super()._candidate_targets(plan, run, spec)

        values: list[str] = []
        tool_name = spec.name.strip().lower()
        for planned, execution in iter_plan_executions(plan, run):
            if execution.state not in {StepExecutionState.PENDING, StepExecutionState.WAITING_APPROVAL}:
                continue
            if planned.tool.strip().lower() != tool_name:
                continue
            candidate = cls._target_for(spec, planned.target)
            if candidate and not any(cls._same_action_target(candidate, existing) for existing in values):
                values.append(candidate)
            if len(values) >= _TARGET_CANDIDATE_LIMIT:
                return tuple(values)

        for candidate in super()._candidate_targets(plan, run, spec):
            if candidate and not any(cls._same_action_target(candidate, existing) for existing in values):
                values.append(candidate)
            if len(values) >= _TARGET_CANDIDATE_LIMIT:
                break
        return tuple(values)

    @classmethod
    def _observed_products(cls, run: MissionRun, target: str | None = None) -> set[str]:
        # Keep WorldModel's product vocabulary even when filtering to one derived
        # target. A finding is also the durable result of a validation observation,
        # and a WEB fact carries HTTP + technology observation semantics. Losing
        # those aliases here made an already validated origin appear incomplete and
        # could trigger a duplicate approval-gated validation action.
        if target is None:
            return set(WorldModel.from_run(run).observed_products)
        products = set(_LegacyCapabilityDirector._observed_products(run, target))
        if "finding" in products:
            products.add("validation_observation")
        if "web_observation" in products:
            products.update({"http_observation", "technology_observation"})
        return products

    def _capability_request(
        self,
        plan: MissionPlan,
        run: MissionRun,
        hypotheses: tuple[Hypothesis, ...],
    ) -> CapabilityRequest:
        registry = self.runtime.registry if self.runtime is not None else None
        model = self._world(run, registry)
        open_hypotheses = [item for item in hypotheses if item.status is HypothesisStatus.OPEN]
        supported = [item for item in hypotheses if item.status is HypothesisStatus.SUPPORTED]

        products: list[str] = list(model.missing_products())
        modalities: list[str] = [
            modality
            for need in model.evidence_needs
            for modality in need.preferred_modalities
            if modality
        ]
        descriptions = [need.description for need in model.evidence_needs if need.description]

        for hypothesis in open_hypotheses:
            metadata = dict(hypothesis.metadata)
            for product in metadata.get("required_products", ()):
                text = str(product)
                if text and text not in products:
                    products.append(text)
            for modality in metadata.get("preferred_modalities", ()):
                text = str(modality)
                if text and text not in modalities:
                    modalities.append(text)
            description = str(metadata.get("evidence_need") or "")
            if description and description not in descriptions:
                descriptions.append(description)

        if supported and not open_hypotheses and not products:
            products = ["validation_observation", "finding"]
            if not modalities:
                modalities = list(model.observed_modalities) or ["http"]
            max_risk = int(RiskLevel.VALIDATION)
            strict = True
            hypothesis_id = supported[0].id
            rationale = "seek bounded validation evidence for the supported hypothesis"
        else:
            max_risk = int(RiskLevel.ACTIVE)
            strict = False
            hypothesis_id = open_hypotheses[0].id if open_hypotheses else (supported[0].id if supported else None)
            rationale = "; ".join(descriptions) or "reduce current mission uncertainty with new evidence"

        return CapabilityRequest.create(
            target=plan.target,
            required_products=products,
            preferred_modalities=modalities,
            max_risk=max_risk,
            require_product_match=strict,
            hypothesis_id=hypothesis_id,
            rationale=rationale,
            expected_info_gain=1.0,
            metadata={
                "authority": "mission_director",
                "open_hypothesis_ids": [item.id for item in open_hypotheses],
                "supported_hypothesis_ids": [item.id for item in supported],
            },
        )

    def _rank_capabilities(
        self,
        plan: MissionPlan,
        run: MissionRun,
        hypotheses: tuple[Hypothesis, ...],
    ) -> list[_CapabilityCandidate]:
        if self.runtime is None:
            return []

        world = self._world(run, self.runtime.registry)
        request = self._capability_request(plan, run, hypotheses)
        resolver = CapabilityResolver(self.runtime.registry, self.runtime.policy)
        observed_modalities = set(world.observed_modalities)
        candidates: list[_CapabilityCandidate] = []
        seen: set[tuple[str, str]] = set()

        # Resolve the abstract evidence need over every evidence-derived target that
        # is meaningful for each adapter. Policy is still evaluated by the resolver,
        # so a discovered hostname/origin does not become executable unless Scope
        # independently authorizes it.
        for adapter in self.runtime.registry:
            spec = adapter.spec
            for target in self._candidate_targets(plan, run, spec):
                scoped_request = replace(request, target=target)
                resolutions = resolver.rank(scoped_request, world=world)
                resolution = next((item for item in resolutions if item.tool == spec.name), None)
                if resolution is None:
                    continue
                key = (resolution.tool, resolution.target)
                if key in seen:
                    continue
                seen.add(key)
                gain, missing = self._information_gain(
                    spec,
                    observed_modalities=observed_modalities,
                    observed_products=self._observed_products(run, resolution.target),
                )
                if gain <= 0:
                    continue
                candidates.append(
                    _RequestedCandidate(
                        spec=spec,
                        target=resolution.target,
                        parameters=dict(resolution.parameters),
                        missing_products=missing,
                        information_gain=gain,
                        utility=resolution.score * max(0.1, gain),
                        requires_approval=resolution.requires_approval,
                        request=scoped_request,
                        resolution=resolution,
                    )
                )

        candidates.sort(key=lambda item: (item.utility, item.information_gain), reverse=True)
        return candidates

    def _candidate_decision(
        self,
        plan: MissionPlan,
        run: MissionRun,
        candidate: _CapabilityCandidate,
        hypotheses: tuple[Hypothesis, ...],
    ) -> ReasoningDecision:
        decision = super()._candidate_decision(plan, run, candidate, hypotheses)
        if not isinstance(candidate, _RequestedCandidate):
            return decision

        request = candidate.request
        resolution = candidate.resolution
        summary = f"{decision.summary} CapabilityRequest {request.id[:8]} resolved to {resolution.tool}."
        if not decision.new_proposals:
            return replace(decision, summary=summary)

        proposal = decision.new_proposals[0]
        enriched = replace(
            proposal,
            metadata={
                **dict(proposal.metadata),
                "capability_request": request.as_dict(),
                "capability_resolution": resolution.as_dict(),
                "guaranteed_products": list(candidate.spec.produces),
                "optional_products": list(candidate.spec.optional_produces),
                "adapter_late_bound": True,
            },
        )
        return replace(decision, summary=summary, new_proposals=(enriched,))

    def decide_next(self, plan: MissionPlan, run: MissionRun, *, approval_tokens=None) -> ReasoningDecision:
        decision = super().decide_next(plan, run, approval_tokens=approval_tokens)
        if decision.action is not ReasoningAction.COMPLETE:
            return decision

        # A resolver with no better adapter must not erase a meaningful existing
        # compatibility action. Reconcile that slot through the same approval/
        # evidence-basis logic before declaring positive completion.
        fallback = self.reasoner.decide(plan, run)
        if fallback.action is not ReasoningAction.CONTINUE or not fallback.next_step_id:
            return decision

        pair = self._planned_step(plan, run, fallback.next_step_id)
        if pair is None:
            return decision
        planned, _ = pair
        spec = self.runtime.registry.get(planned.tool).spec if self.runtime is not None else None
        if spec is not None:
            gain, _ = self._information_gain(
                spec,
                observed_modalities=self._observed_modalities(plan, run),
                observed_products=self._observed_products(run, planned.target),
            )
            if gain <= 0:
                return ReasoningDecision.create(
                    action=ReasoningAction.SKIP,
                    summary="The remaining compatibility action cannot add a missing evidence product; retire it.",
                    next_step_id=planned.id,
                    hypotheses=decision.hypotheses,
                )

        normalized = replace(fallback, hypotheses=decision.hypotheses)
        return self._normalize_approval(plan, run, normalized, approval_tokens or {})