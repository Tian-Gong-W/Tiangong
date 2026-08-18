from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tonmen.agents import AdaptiveMissionPlanner
from tonmen.ai import AIAdvisory, AIHypothesis, AIProviderError, OllamaProvider
from tonmen.core.config import TonmenConfig, validate_local_ai_base_url, validate_local_ai_model
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import EvidenceRecord, GraphNode
from tonmen.missions import MissionPlan, MissionRun


@contextmanager
def fake_ollama():
    state: dict[str, object] = {"requests": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def _json(self, payload):
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            state["requests"].append({"method": "GET", "path": self.path, "authorization": self.headers.get("Authorization")})
            if self.path == "/api/tags":
                self._json({"models": [{"name": "test-model", "model": "test-model"}]})
                return
            self.send_error(404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            state["requests"].append(
                {
                    "method": "POST",
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "payload": payload,
                }
            )
            if self.path == "/api/chat":
                content = {
                    "summary": "Web evidence is consistent enough for further deterministic analysis.",
                    "focus": ["corroborate web surface"],
                    "hypotheses": [
                        {
                            "key": "local_review",
                            "summary": "Review the observed web evidence.",
                            "confidence": 0.7,
                            "basis_fact_ids": ["fact-1", "invented-fact"],
                        }
                    ],
                    "challenge_decision": False,
                    "challenge_reason": "",
                    "basis_fact_ids": ["fact-1", "invented-fact"],
                }
                self._json({"message": {"role": "assistant", "content": json.dumps(content)}})
                return
            self.send_error(404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_local_ai_defaults_disabled_and_has_no_api_key_field(tmp_path):
    config = TonmenConfig(workspace=tmp_path)

    assert config.ai_enabled is False
    assert config.ai_provider == "none"
    assert not any("key" in name.lower() for name in config.__dataclass_fields__)

    path = config.save(tmp_path / "tonmen.toml")
    text = path.read_text(encoding="utf-8")
    assert "[ai]" in text
    assert "enabled = false" in text
    assert "api_key" not in text.lower()


def test_local_ai_rejects_non_loopback_credentials_paths_and_cloud_models():
    for value in (
        "https://127.0.0.1:11434",
        "http://example.com:11434",
        "http://user:pass@127.0.0.1:11434",
        "http://127.0.0.1:11434/api",
    ):
        with pytest.raises(ValueError):
            validate_local_ai_base_url(value)

    assert validate_local_ai_model("qwen3:8b") == "qwen3:8b"
    with pytest.raises(ValueError, match="cloud"):
        validate_local_ai_model("gpt-oss:120b-cloud")
    with pytest.raises(ValueError, match="cloud"):
        OllamaProvider(base_url="http://127.0.0.1:11434", model="glm-4.7:cloud")


def test_config_loads_explicit_no_key_local_ollama(tmp_path):
    path = tmp_path / "tonmen.toml"
    path.write_text(
        """[tonmen]\nworkspace = '.tonmen'\n\n[scope]\nallowed_targets = []\ndenied_targets = []\n\n[ai]\nenabled = true\nprovider = 'ollama'\nmodel = 'test-model'\nbase_url = 'http://127.0.0.1:11434'\ntimeout_seconds = 12\n""",
        encoding="utf-8",
    )

    config = TonmenConfig.load(path)

    assert config.ai_enabled is True
    assert config.ai_provider == "ollama"
    assert config.ai_model == "test-model"
    assert config.ai_timeout_seconds == 12


def test_ollama_status_and_advisory_are_no_key_structured_and_fact_bounded():
    with fake_ollama() as (base_url, state):
        provider = OllamaProvider(base_url=base_url, model="test-model", timeout_seconds=3)

        status = provider.status()
        advisory = provider.advise(
            {"facts": [{"id": "fact-1", "label": "observed"}]},
            allowed_fact_ids={"fact-1"},
        )

    assert status.ready is True
    assert status.api_key_required is False
    assert status.local_only is True
    assert advisory.execution_authority is False
    assert advisory.local_only is True
    assert advisory.basis_fact_ids == ("fact-1",)
    assert advisory.hypotheses[0].basis_fact_ids == ("fact-1",)

    requests = state["requests"]
    assert requests[0]["path"] == "/api/tags"
    chat = next(item for item in requests if item["path"] == "/api/chat")
    assert chat["authorization"] is None
    assert chat["payload"]["stream"] is False
    assert isinstance(chat["payload"]["format"], dict)
    assert chat["payload"]["options"]["temperature"] == 0
    system_prompt = chat["payload"]["messages"][0]["content"]
    user_context = chat["payload"]["messages"][1]["content"]
    assert "NO execution authority" in system_prompt
    assert "argv" not in user_context
    assert "stdout" not in user_context
    assert "stderr" not in user_context


def _run_with_evidence(tmp_path):
    config = TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",))
    runtime = TonmenRuntime.sentinel(config)
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.graph.add_node(GraphNode(id=run.id, kind="mission", label="mission:localhost", metadata={"plan_id": plan.id}))
    run.graph.add_node(
        GraphNode(
            id="fact-1",
            kind="intelligence.web",
            label="http://localhost [200]",
            metadata={
                "source": "httpx",
                "target": "http://localhost",
                "confidence": 1.0,
                "severity": "info",
                "data": {"url": "http://localhost", "status_code": 200},
            },
        )
    )
    now = datetime.now(timezone.utc)
    run.evidence.append(
        EvidenceRecord(
            id="evidence-1",
            tool="httpx",
            target="localhost",
            argv=("httpx", "-u", "localhost"),
            exit_code=0,
            stdout="http://localhost [200]",
            stderr="",
            started_at=now,
            finished_at=now,
        )
    )
    return runtime, plan, run


def test_strategy_records_local_ai_advisory_without_plan_or_execution_authority(tmp_path):
    runtime, plan, run = _run_with_evidence(tmp_path)

    class FakeAI:
        enabled = True

        def advise(self, plan, run, decision=None):
            return AIAdvisory(
                provider="ollama",
                model="test-model",
                summary="Advisory only.",
                focus=("web evidence",),
                hypotheses=(AIHypothesis("h1", "Review fact", 0.8, ("fact-1",)),),
                challenge_decision=True,
                challenge_reason="Double-check the evidence.",
                basis_fact_ids=("fact-1",),
            )

    runtime.ai = FakeAI()
    before_steps = tuple(plan.steps)
    planner = AdaptiveMissionPlanner(runtime)

    planner._record_local_ai_advisory(plan, run)

    advisory = next(node for node in run.graph.nodes.values() if node.kind == "ai.advisory")
    assert tuple(plan.steps) == before_steps
    assert advisory.metadata["execution_authority"] is False
    assert advisory.metadata["local_only"] is True
    assert advisory.metadata["api_key_required"] is False
    assert advisory.metadata["basis_fact_ids"] == ["fact-1"]
    assert any(edge.source == "fact-1" and edge.relation == "supports_ai_advisory" for edge in run.graph.edges)


def test_strategy_ai_failure_records_fallback_and_does_not_raise(tmp_path):
    runtime, plan, run = _run_with_evidence(tmp_path)

    class FailingAI:
        enabled = True

        def advise(self, plan, run, decision=None):
            raise AIProviderError("local model unavailable")

    runtime.ai = FailingAI()
    planner = AdaptiveMissionPlanner(runtime)

    planner._record_local_ai_advisory(plan, run)

    error = next(node for node in run.graph.nodes.values() if node.kind == "ai.advisory_error")
    assert error.metadata["fallback"] == "deterministic"
    assert error.metadata["execution_authority"] is False
    assert error.metadata["local_only"] is True
