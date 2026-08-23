from __future__ import annotations

import json

from tonmen.agents import AdaptiveMissionPlanner
from tonmen.ai import AIAdvisory, OllamaProvider
from tonmen.capabilities import CapabilityCandidate


def _candidate(tool: str, score: float, *, eligible: bool = True, risk: int = 1):
    return CapabilityCandidate(
        tool=tool,
        target="localhost",
        parameters={},
        eligible=eligible,
        score=score,
        rationale=f"{tool} rationale",
        expected_information_gain=f"{tool} evidence",
        basis_fact_ids=("fact-1",),
        reasons=(f"deterministic score={score:.3f}",),
        provides=(f"{tool}.observe",),
        requires_capabilities=(),
        resolves_unknowns=(),
        risk=risk,
        requires_approval=False,
        readiness_code="ready",
    )


def test_near_tie_can_be_reordered_only_by_bounded_ai_adjustment():
    rankings = (
        _candidate("base-winner", 80.0),
        _candidate("near-alternative", 77.0),
    )
    preferences = {
        "base-winner": {"preference": -1.0, "rationale": "less useful now"},
        "near-alternative": {"preference": 1.0, "rationale": "closes current uncertainty"},
    }

    selected, rows, result = AdaptiveMissionPlanner._select_candidate(rankings, preferences)

    assert selected is not None
    assert selected.tool == "near-alternative"
    assert result["changed_selection"] is True
    assert result["selection_engine"] == "capability_catalog+bounded_ai_tiebreak"
    by_tool = {row["tool"]: row for row in rows}
    assert by_tool["base-winner"]["ai_adjustment"] == -2.5
    assert by_tool["near-alternative"]["ai_adjustment"] == 2.5
    assert by_tool["near-alternative"]["final_score"] == 79.5


def test_ai_cannot_overcome_candidate_outside_deterministic_tiebreak_window():
    rankings = (
        _candidate("base-winner", 80.0),
        _candidate("far-alternative", 74.0),
    )
    preferences = {
        "base-winner": {"preference": -1.0, "rationale": "prefer other"},
        "far-alternative": {"preference": 1.0, "rationale": "prefer this"},
    }

    selected, rows, result = AdaptiveMissionPlanner._select_candidate(rankings, preferences)

    assert selected is not None
    assert selected.tool == "base-winner"
    by_tool = {row["tool"]: row for row in rows}
    assert by_tool["far-alternative"]["within_ai_tiebreak_window"] is False
    assert by_tool["far-alternative"]["ai_adjustment"] == 0.0
    assert result["changed_selection"] is False


def test_ai_never_makes_ineligible_candidate_selectable():
    rankings = (
        _candidate("eligible", 50.0, eligible=True),
        _candidate("policy-blocked", 500.0, eligible=False, risk=5),
    )
    preferences = {
        "policy-blocked": {"preference": 1.0, "rationale": "model tried to prefer blocked item"},
        "eligible": {"preference": -1.0, "rationale": "model dislikes it"},
    }

    selected, rows, _ = AdaptiveMissionPlanner._select_candidate(rankings, preferences)

    assert selected is not None
    assert selected.tool == "eligible"
    blocked = next(row for row in rows if row["tool"] == "policy-blocked")
    assert blocked["eligible"] is False
    assert blocked["ai_adjustment"] == 0.0


def test_ollama_filters_unknown_candidate_tools_and_fact_ids():
    provider = OllamaProvider(base_url="http://127.0.0.1:11434", model="test-model")
    content = {
        "summary": "candidate preference",
        "focus": [],
        "hypotheses": [],
        "challenge_decision": False,
        "challenge_reason": "",
        "basis_fact_ids": ["fact-1", "invented"],
        "capability_preferences": [
            {
                "tool": "known-tool",
                "preference": 0.8,
                "rationale": "supported by current fact",
                "basis_fact_ids": ["fact-1", "invented"],
            },
            {
                "tool": "invented-tool",
                "preference": 1.0,
                "rationale": "must be rejected",
                "basis_fact_ids": ["fact-1"],
            },
        ],
    }
    provider._request_json = lambda path, payload=None: {
        "message": {"role": "assistant", "content": json.dumps(content)}
    }

    advisory = provider.advise(
        {"catalog_candidates": [{"tool": "known-tool"}]},
        allowed_fact_ids={"fact-1"},
        allowed_candidate_tools={"known-tool"},
    )

    assert advisory.basis_fact_ids == ("fact-1",)
    assert [item.tool for item in advisory.capability_preferences] == ["known-tool"]
    assert advisory.capability_preferences[0].basis_fact_ids == ("fact-1",)
    assert advisory.execution_authority is False


def test_ai_advisory_default_remains_backward_compatible_without_preferences():
    advisory = AIAdvisory(
        provider="test",
        model="test",
        summary="legacy advisory",
        focus=(),
        hypotheses=(),
        challenge_decision=False,
        challenge_reason="",
        basis_fact_ids=(),
    )

    assert advisory.capability_preferences == ()
    assert advisory.execution_authority is False
