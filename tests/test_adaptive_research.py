from __future__ import annotations

import subprocess

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.director import AdaptiveMissionDirector
from tonmen.research import ActionRecord, ActionState
from tonmen.tools import CapabilitySpec, RiskLevel, ToolSpec


def _asset_set(target, scope):
    return {
        "target": target,
        "assets": [],
        "authorized_addresses": [],
        "needs_scope": [],
        "semantics": {"dns_resolution_expands_scope": False},
    }


def _runtime(tmp_path):
    return TonmenRuntime.sentinel(
        TonmenConfig(
            workspace=tmp_path,
            allowed_targets=("example.test",),
        )
    )


def test_legacy_tool_spec_exposes_semantic_capability_without_granting_authority():
    spec = ToolSpec(
        name="observe",
        category="research.observe",
        description="observe a governed target",
        risk=RiskLevel.DISCOVERY,
        capabilities=("surface.observe",),
    )

    capability = spec.as_capability()

    assert isinstance(capability, CapabilitySpec)
    assert capability.name == "observe"
    assert capability.capabilities == ("surface.observe",)
    assert capability.risk is RiskLevel.DISCOVERY
    assert capability.replayable is True


def test_bootstrap_creates_a_minimal_action_instead_of_a_full_future_script(tmp_path):
    runtime = _runtime(tmp_path)
    planner = MissionPlanner(runtime, asset_resolver=_asset_set)

    bootstrap = planner.bootstrap("https://example.test")

    assert len(bootstrap.initial_hypotheses) == 1
    assert len(bootstrap.initial_actions) == 1
    assert bootstrap.metadata["planner_mode"] == "adaptive"
    assert bootstrap.initial_actions[0].risk < RiskLevel.VALIDATION

    # The compatibility facade deliberately keeps the old three-step behavior
    # while CLI/Chronicle migrate to the adaptive Director.
    legacy = planner.plan("https://example.test")
    assert [step.tool for step in legacy.steps] == ["nmap", "httpx", "nuclei"]
    assert legacy.metadata["planner_mode"] == "legacy"


def test_decide_next_generates_a_new_non_duplicate_action_from_current_state(tmp_path):
    runtime = _runtime(tmp_path)
    planner = MissionPlanner(runtime, asset_resolver=_asset_set)
    state = planner.create_state("https://example.test")

    first = planner.decide_next(state).best
    assert first is not None
    state.action_ledger.append(ActionRecord(proposal=first, state=ActionState.SUCCEEDED, evidence_id="ev-1"))
    state.evidence_ids.append("ev-1")

    second_decision = planner.decide_next(state)
    second = second_decision.best

    assert second is not None
    assert second.signature != first.signature
    assert all(candidate.signature != first.signature for candidate in second_decision.candidates)
    assert "no fixed next-step ID" in second_decision.explanation


def test_director_replans_after_each_execution_and_preserves_runtime_governance(tmp_path):
    runtime = _runtime(tmp_path)
    planner = MissionPlanner(runtime, asset_resolver=_asset_set)
    director = AdaptiveMissionDirector(runtime, planner)

    assert runtime.executor is not None
    runtime.executor._runner = lambda *args, **kwargs: subprocess.CompletedProcess(
        args=args[0],
        returncode=0,
        stdout="ok\n",
        stderr="",
    )

    state = director.start("https://example.test")
    first = director.tick(state)
    second = director.tick(state)

    assert first.outcome == "executed"
    assert second.outcome == "executed"
    assert len(state.action_ledger) == 2
    assert state.action_ledger[0].signature != state.action_ledger[1].signature
    assert len(state.evidence_ids) == 2
    assert all(record.state is ActionState.SUCCEEDED for record in state.action_ledger)

    # Once lower-risk observations exist, the planner may propose validation work,
    # but the Director still stops at the existing Approval boundary.
    third = director.tick(state)
    assert third.outcome in {"approval_required", "converged"}
    if third.outcome == "approval_required":
        waiting = state.action_ledger[-1]
        assert waiting.state is ActionState.WAITING_APPROVAL
        assert waiting.proposal.requires_approval is True
