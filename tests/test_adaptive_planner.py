from __future__ import annotations

from dataclasses import replace

from tonmen.agents import AdaptivePlanningState, MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.hypotheses import HypothesisStatus
from tonmen.tools import CapabilitySpec


def _runtime(tmp_path):
    return TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))


def test_builtin_tools_are_semantic_capabilities(tmp_path):
    runtime = _runtime(tmp_path)
    specs = {adapter.spec.name: adapter.spec for adapter in runtime.registry}
    assert isinstance(specs["nmap"], CapabilitySpec)
    assert specs["nmap"].modalities == ("network",)
    assert specs["httpx"].accepts == ("url", "host")
    assert specs["nuclei"].requires_approval is True


def test_bootstrap_is_small_low_risk_and_hypothesis_driven(tmp_path):
    runtime = _runtime(tmp_path)
    result = MissionPlanner(runtime).bootstrap("localhost")
    assert len(result.initial_hypotheses) == 1
    assert result.initial_hypotheses[0].status is HypothesisStatus.OPEN
    assert 1 <= len(result.initial_actions) <= 2
    assert all(not action.requires_approval for action in result.initial_actions)
    assert all(action.hypothesis_ids == (result.initial_hypotheses[0].id,) for action in result.initial_actions)


def test_decide_next_abandons_attempted_capability_and_switches_path(tmp_path):
    runtime = _runtime(tmp_path)
    planner = MissionPlanner(runtime)
    bootstrap = planner.bootstrap("localhost")
    first = bootstrap.initial_actions[0]
    state = AdaptivePlanningState(
        target="localhost",
        hypotheses=bootstrap.initial_hypotheses,
        attempted_capabilities=(first.capability,),
        observed_modalities=tuple(runtime.registry.get(first.capability).spec.modalities),
        remaining_executions=4,
    )
    decision = planner.decide_next(state)
    assert decision.candidates
    assert all(candidate.capability != first.capability for candidate in decision.candidates)
    assert any(
        set(runtime.registry.get(candidate.capability).spec.modalities) - set(state.observed_modalities)
        for candidate in decision.candidates
    )


def test_validation_is_not_proposed_until_a_hypothesis_is_supported(tmp_path):
    runtime = _runtime(tmp_path)
    planner = MissionPlanner(runtime)
    bootstrap = planner.bootstrap("localhost")
    open_state = AdaptivePlanningState(
        target="localhost",
        hypotheses=bootstrap.initial_hypotheses,
        attempted_capabilities=("nmap", "httpx"),
        observed_modalities=("network", "http", "text"),
        remaining_executions=4,
    )
    assert planner.decide_next(open_state).candidates == ()
    supported = replace(bootstrap.initial_hypotheses[0], status=HypothesisStatus.SUPPORTED, confidence=0.8)
    supported_state = replace(open_state, hypotheses=(supported,))
    decision = planner.decide_next(supported_state)
    assert decision.candidates
    assert decision.candidates[0].capability == "nuclei"
    assert decision.candidates[0].requires_approval is True


def test_legacy_plan_keeps_current_execution_order(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    assert [step.tool for step in plan.steps] == ["nmap", "httpx", "nuclei"]
