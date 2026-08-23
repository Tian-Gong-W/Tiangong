from __future__ import annotations

from tonmen.chronicle import ChronicleStore
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.loop import LoopStopReason, MissionLoop, MissionLoopPolicy
from tonmen.missions import (
    ActionLedger,
    MissionPlan,
    MissionRun,
    MissionRunState,
    MissionStep,
    StepExecutionState,
)
from tonmen.reasoning import ReasoningAction, ReasoningDecision


def _empty_plan() -> MissionPlan:
    return MissionPlan.create("localhost", [])


def _runtime(tmp_path) -> TonmenRuntime:
    return TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))


class _StaticDirector:
    def __init__(self, action: ReasoningAction) -> None:
        self.action = action

    def decide_next(self, plan, run, *, approval_tokens=None):
        return ReasoningDecision.create(
            action=self.action,
            summary=f"test decision: {self.action.value}",
            next_step_id="missing" if self.action is ReasoningAction.SKIP else None,
        )


def test_action_ledger_round_trips_through_existing_chronicle_schema(tmp_path):
    plan = MissionPlan.create(
        "localhost",
        [
            MissionStep.create(
                tool="nmap",
                target="localhost",
                parameters={},
                risk=1,
                requires_approval=False,
                rationale="compatibility slot",
            )
        ],
    )
    run = MissionRun.create(plan)
    ledger = ActionLedger(run.steps, legacy_slots=len(plan.steps))
    dynamic = ledger.append_dynamic(
        action_id="dynamic:proposal-1",
        tool="httpx",
        target="localhost",
        proposal_id="proposal-1",
        state=StepExecutionState.WAITING_APPROVAL,
        metadata={"requires_approval": True},
        error="explicit approval grant required",
    )

    store = ChronicleStore(tmp_path)
    store.save(plan, run)
    loaded_plan, loaded_run = store.load(run.id)
    loaded = ActionLedger(loaded_run.steps, legacy_slots=len(loaded_plan.steps))

    assert len(loaded.legacy) == 1
    assert len(loaded.dynamic) == 1
    assert loaded.dynamic[0].id == dynamic.id
    assert loaded.dynamic_for_proposal("proposal-1") is loaded.dynamic[0]
    assert loaded.waiting_for_approval() is loaded.dynamic[0]


def test_no_executable_action_stops_session_without_false_success(tmp_path):
    loop = MissionLoop(_runtime(tmp_path), MissionLoopPolicy(max_iterations=4, max_executions=1))
    loop.director = _StaticDirector(ReasoningAction.NO_ACTION)

    result = loop.run(_empty_plan())

    assert result.stop_reason is LoopStopReason.NO_EXECUTABLE_ACTION
    assert result.iterations == 1
    assert result.run.state is MissionRunState.RUNNING
    assert result.run.finished_at is None
    stops = [node for node in result.run.graph.nodes.values() if node.kind == "loop.stop"]
    assert stops[-1].metadata["reason"] == "no_executable_action"


def test_convergence_detector_now_terminates_the_live_loop(tmp_path):
    loop = MissionLoop(_runtime(tmp_path), MissionLoopPolicy(max_iterations=5, max_executions=1, max_repeat_decisions=4))
    loop.director = _StaticDirector(ReasoningAction.SKIP)

    result = loop.run(_empty_plan())

    assert result.stop_reason is LoopStopReason.CONVERGED
    assert result.iterations == 2
    assert result.run.state is MissionRunState.RUNNING
    stops = [node for node in result.run.graph.nodes.values() if node.kind == "loop.stop"]
    assert stops[-1].metadata["reason"] == "converged"


def test_complete_is_reserved_for_positive_mission_completion(tmp_path):
    loop = MissionLoop(_runtime(tmp_path), MissionLoopPolicy(max_iterations=3, max_executions=1))
    loop.director = _StaticDirector(ReasoningAction.COMPLETE)

    result = loop.run(_empty_plan())

    assert result.stop_reason is LoopStopReason.COMPLETE
    assert result.run.state is MissionRunState.SUCCEEDED
    assert result.run.finished_at is not None
