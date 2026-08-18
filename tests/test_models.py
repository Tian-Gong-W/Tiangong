from __future__ import annotations

import json

import pytest

from tonmen.council import AssessmentCouncil
from tonmen.missions import MissionPlan, MissionRun, MissionStep
from tonmen.models import ModelAgentReview, ModelRuntime, ModelRuntimeConfig, ModelRuntimeError
from tonmen.tools import RiskLevel


class _Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, maximum):
        return self.payload[:maximum]


class _FakeModelRuntime:
    def __init__(self, *, max_calls=50):
        self.config = ModelRuntimeConfig(provider="ollama", model="local-test", max_calls=max_calls)
        self.calls = []

    @property
    def enabled(self):
        return True

    def review(self, *, role, focus, target_profile, allowed_capabilities, calls_already_used):
        if calls_already_used >= self.config.max_calls:
            raise ModelRuntimeError("model call budget exhausted")
        self.calls.append((role, focus, calls_already_used, tuple(allowed_capabilities)))
        return ModelAgentReview(
            role=role,
            summary=f"model review for {role}",
            observations=("evidence-linked observation",),
            risks=("review risk",),
            next_questions=("what remains unknown",),
            recommended_capabilities=tuple(allowed_capabilities[:1]),
            confidence=0.8,
            prompt_tokens=12,
            output_tokens=8,
        )


def _plan_and_run():
    plan = MissionPlan.create(
        "localhost",
        [
            MissionStep.create(
                tool="nmap",
                target="localhost",
                parameters={"ports": (80, 443)},
                risk=int(RiskLevel.DISCOVERY),
                requires_approval=False,
                rationale="network candidate",
            ),
            MissionStep.create(
                tool="crawler",
                target="localhost",
                parameters={"max_pages": 25, "max_depth": 2, "timeout": 10},
                risk=int(RiskLevel.DISCOVERY),
                requires_approval=False,
                rationale="web candidate",
            ),
        ],
    )
    return plan, MissionRun.create(plan)


def test_model_config_defaults_to_no_model_and_rejects_remote_ollama():
    assert ModelRuntimeConfig().enabled is False
    with pytest.raises(ValueError, match="loopback"):
        ModelRuntimeConfig(provider="ollama", model="qwen3", base_url="http://example.com:11434/api")
    with pytest.raises(ValueError, match="max_calls"):
        ModelRuntimeConfig(provider="ollama", model="qwen3", max_calls=51)


def test_ollama_runtime_uses_structured_output_and_filters_capability_proposals(monkeypatch):
    response = {
        "message": {
            "role": "assistant",
            "content": json.dumps(
                {
                    "summary": "bounded review",
                    "observations": ["one"],
                    "risks": ["two"],
                    "next_questions": ["three"],
                    "recommended_capabilities": ["crawler", "not-allowed"],
                    "confidence": 0.75,
                }
            ),
        },
        "prompt_eval_count": 21,
        "eval_count": 13,
    }
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _Response(response)

    monkeypatch.setattr("tonmen.models.runtime.urlopen", fake_urlopen)
    runtime = ModelRuntime(ModelRuntimeConfig(provider="ollama", model="qwen3"))
    review = runtime.review(
        role="web_surface_analyst",
        focus="web_surface",
        target_profile={"target_kind": "web", "unknowns": ["routes"]},
        allowed_capabilities=("nmap", "crawler"),
        calls_already_used=0,
    )

    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["body"]["stream"] is False
    assert isinstance(captured["body"]["format"], dict)
    assert "tools" not in captured["body"]
    assert review is not None
    assert review.recommended_capabilities == ("crawler",)
    assert review.prompt_tokens == 21
    assert review.output_tokens == 13


def test_council_uses_model_subagents_but_never_gives_execution_authority():
    plan, run = _plan_and_run()
    model = _FakeModelRuntime(max_calls=5)
    council = AssessmentCouncil(target_rounds=7, agents_per_round=3, model_runtime=model)

    round_id = council.record_round(plan, run, session_id="session", phase="live")

    assert round_id is not None
    agents = [node for node in run.graph.nodes.values() if node.kind == "council.subagent"]
    calls = [node for node in run.graph.nodes.values() if node.kind == "model.call"]
    assert len(agents) == 3
    assert len(model.calls) == 3
    assert len(calls) == 3
    assert all(node.metadata["agent_mode"] == "model" for node in agents)
    assert all(node.metadata["execution_authority"] is False for node in agents)
    assert all(node.metadata["report_only"] is True for node in agents)
    assert all(node.metadata["execution_authority"] is False for node in calls)


def test_model_call_budget_forces_deterministic_fallback():
    plan, run = _plan_and_run()
    model = _FakeModelRuntime(max_calls=2)
    council = AssessmentCouncil(target_rounds=7, agents_per_round=3, model_runtime=model)

    council.record_round(plan, run, session_id="session", phase="live")

    agents = [node for node in run.graph.nodes.values() if node.kind == "council.subagent"]
    assert len(model.calls) == 2
    assert [node.metadata["agent_mode"] for node in agents].count("model") == 2
    fallback = [node for node in agents if node.metadata["agent_mode"] == "deterministic"]
    assert len(fallback) == 1
    assert "budget exhausted" in fallback[0].metadata["model_error"]
