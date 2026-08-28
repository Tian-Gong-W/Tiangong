from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from tonmen.agents import MissionCoordinator, MissionPlanner
from tonmen.chronicle import ChronicleStore
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import EvidenceRecord
from tonmen.intelligence import FactKind, Severity, parse_evidence
from tonmen.jobs import JobManager
from tonmen.missions import MissionRunState


def _evidence(tool: str, stdout: str, target: str = "localhost") -> EvidenceRecord:
    now = datetime.now(timezone.utc)
    return EvidenceRecord(
        id=f"e-{tool}",
        tool=tool,
        target=target,
        argv=(tool,),
        exit_code=0,
        stdout=stdout,
        stderr="",
        started_at=now,
        finished_at=now,
    )


def test_nmap_output_becomes_host_and_service_facts():
    facts = parse_evidence(
        _evidence(
            "nmap",
            """Nmap scan report for localhost (127.0.0.1)
Host is up (0.00010s latency).
PORT    STATE SERVICE  VERSION
80/tcp  open  http     nginx 1.24.0
443/tcp open  ssl/http nginx 1.24.0
""",
        )
    )
    assert [fact.kind for fact in facts].count(FactKind.SERVICE) == 2
    service = next(fact for fact in facts if fact.kind is FactKind.SERVICE and fact.data["port"] == 443)
    assert service.data["service"] == "ssl/http"
    assert service.evidence_id == "e-nmap"


def test_subfinder_output_becomes_deduplicated_domain_facts():
    facts = parse_evidence(
        _evidence("subfinder", "api.example.test\nWWW.example.test.\napi.example.test\n", "example.test")
    )
    assert [fact.kind for fact in facts] == [FactKind.DOMAIN, FactKind.DOMAIN]
    assert [fact.data["host"] for fact in facts] == ["api.example.test", "www.example.test"]
    assert all(fact.data["root_target"] == "example.test" for fact in facts)


def test_httpx_output_becomes_web_fact():
    facts = parse_evidence(_evidence("httpx", "https://localhost [200] [Welcome] [nginx,React]\n"))
    assert len(facts) == 1
    assert facts[0].kind is FactKind.WEB
    assert facts[0].data["status_code"] == 200
    assert facts[0].data["technologies"] == ["nginx", "React"]


def test_katana_output_becomes_deduplicated_endpoint_facts():
    facts = parse_evidence(
        _evidence(
            "katana",
            "https://example.test/api/users?id=1\nhttps://example.test/static/app.js#fragment\nhttps://example.test/api/users?id=1\n",
            "https://example.test",
        )
    )
    assert [fact.kind for fact in facts] == [FactKind.ENDPOINT, FactKind.ENDPOINT]
    assert facts[0].data["path"] == "/api/users"
    assert facts[0].data["query"] == "id=1"
    assert facts[1].data["url"] == "https://example.test/static/app.js"


def test_nuclei_jsonl_becomes_finding():
    line = json.dumps(
        {
            "template-id": "demo-check",
            "info": {"name": "Demo Exposure", "severity": "high"},
            "matched-at": "https://localhost/demo",
            "type": "http",
        }
    )
    facts = parse_evidence(_evidence("nuclei", line + "\n"))
    assert len(facts) == 1
    assert facts[0].kind is FactKind.FINDING
    assert facts[0].severity is Severity.HIGH
    assert facts[0].data["template_id"] == "demo-check"


def _runtime(tmp_path, calls):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))

    def fake_runner(argv, **kwargs):
        calls.append(list(argv))
        output = {
            "nmap": """Nmap scan report for localhost
Host is up.
PORT   STATE SERVICE VERSION
80/tcp open  http    nginx 1.24.0
""",
            "subfinder": "api.localhost\n",
            "httpx": "https://localhost [200] [Welcome] [nginx]\n",
            "katana": "https://localhost/\nhttps://localhost/api/status\n",
            "nuclei": json.dumps(
                {
                    "template-id": "demo-check",
                    "info": {"name": "Demo Exposure", "severity": "medium"},
                    "matched-at": "https://localhost/demo",
                    "type": "http",
                }
            )
            + "\n",
        }[argv[0]]
        return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    return runtime


def test_intelligence_survives_chronicle_and_approved_resume(tmp_path):
    calls1: list[list[str]] = []
    runtime1 = _runtime(tmp_path, calls1)
    plan = MissionPlanner(runtime1).plan("localhost")
    run = MissionCoordinator(runtime1).run(plan)

    assert run.state is MissionRunState.WAITING_APPROVAL
    kinds = {node.kind for node in run.graph.nodes.values()}
    assert "intelligence.service" in kinds
    assert "intelligence.web" in kinds
    assert "intelligence.domain" in kinds
    assert "intelligence.endpoint" in kinds
    assert "nuclei" not in [call[0] for call in calls1]

    store = ChronicleStore(tmp_path)
    store.save(plan, run)
    loaded_plan, loaded_run = store.load(run.id)
    persisted = {node.kind for node in loaded_run.graph.nodes.values()}
    assert "intelligence.service" in persisted
    assert "intelligence.web" in persisted
    assert "intelligence.domain" in persisted
    assert "intelligence.endpoint" in persisted

    calls2: list[list[str]] = []
    runtime2 = _runtime(tmp_path, calls2)
    waiting = next(step for step in loaded_plan.steps if step.tool == "nuclei")
    grant = runtime2.approvals.issue(tool=waiting.tool, target=waiting.target)
    MissionCoordinator(runtime2).resume(
        loaded_plan,
        loaded_run,
        approval_tokens={waiting.id: grant.token},
    )

    assert loaded_run.state is MissionRunState.SUCCEEDED
    assert "nuclei" in [call[0] for call in calls2]
    findings = [
        node
        for node in loaded_run.graph.nodes.values()
        if node.kind == "intelligence.finding"
    ]
    assert len(findings) == 1
    assert findings[0].metadata["severity"] == "medium"
    assert findings[0].metadata["evidence_id"]
