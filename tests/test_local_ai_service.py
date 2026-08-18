from __future__ import annotations

from tonmen.ai import AIAdvisory, LocalAIService
from tonmen.core.config import TonmenConfig
from tonmen.missions import MissionPlan, MissionRun


def test_pre_reasoning_advisory_cannot_claim_it_challenges_a_missing_decision(tmp_path):
    service = LocalAIService(TonmenConfig(workspace=tmp_path))

    class FakeProvider:
        def advise(self, context, *, allowed_fact_ids):
            assert context["phase"] == "pre_reasoning_advisory"
            assert context["deterministic_decision"] is None
            return AIAdvisory(
                provider="ollama",
                model="test-model",
                summary="Review the current evidence.",
                focus=("evidence quality",),
                hypotheses=(),
                challenge_decision=True,
                challenge_reason="There is no decision yet, so this must be normalized.",
                basis_fact_ids=(),
            )

    service.provider = FakeProvider()
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)

    advisory = service.advise(plan, run)

    assert advisory is not None
    assert advisory.challenge_decision is False
    assert advisory.challenge_reason == ""
    assert advisory.execution_authority is False
