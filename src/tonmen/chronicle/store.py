from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tonmen.evidence import EvidenceGraph, EvidenceRecord, GraphNode
from tonmen.missions import (
    MissionPlan,
    MissionRun,
    MissionRunState,
    MissionStep,
    StepExecution,
    StepExecutionState,
    StepState,
)
from tonmen.observations import Observation

_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ChronicleEntry:
    run_id: str
    plan_id: str
    target: str
    state: MissionRunState
    started_at: datetime
    finished_at: datetime | None


class ChronicleStore:
    """Private, atomic local persistence for mission plans, runtime state and evidence."""

    def __init__(self, workspace: Path) -> None:
        self.root = Path(workspace) / "missions"

    def _ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    @staticmethod
    def _validate_run_id(run_id: str) -> str:
        value = run_id.strip().lower()
        if len(value) != 32 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("invalid mission run id")
        return value

    def _path(self, run_id: str) -> Path:
        return self.root / f"{self._validate_run_id(run_id)}.json"

    def save(self, plan: MissionPlan, run: MissionRun) -> Path:
        if run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")
        self._ensure_root()
        path = self._path(run.id)
        temp = path.with_suffix(".tmp")
        payload = {"schema": _SCHEMA_VERSION, "plan": self._plan_to_dict(plan), "run": self._run_to_dict(run)}
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(temp, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write("\n")
        except Exception:
            try:
                temp.unlink()
            except OSError:
                pass
            raise
        os.replace(temp, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return path

    def load(self, run_id: str) -> tuple[MissionPlan, MissionRun]:
        path = self._path(run_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != _SCHEMA_VERSION:
            raise ValueError("unsupported chronicle schema")
        return self._plan_from_dict(payload["plan"]), self._run_from_dict(payload["run"])

    def delete(self, run_id: str) -> bool:
        """Delete one persisted mission record after validating its run id."""
        path = self._path(run_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    def list(self) -> list[ChronicleEntry]:
        if not self.root.exists():
            return []
        entries: list[ChronicleEntry] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                run = payload["run"]
                entries.append(
                    ChronicleEntry(
                        run_id=run["id"],
                        plan_id=run["plan_id"],
                        target=run["target"],
                        state=MissionRunState(run["state"]),
                        started_at=datetime.fromisoformat(run["started_at"]),
                        finished_at=datetime.fromisoformat(run["finished_at"]) if run.get("finished_at") else None,
                    )
                )
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return sorted(entries, key=lambda entry: entry.started_at, reverse=True)

    @staticmethod
    def _plan_to_dict(plan: MissionPlan) -> dict[str, Any]:
        return {
            "id": plan.id,
            "target": plan.target,
            "steps": [
                {
                    "id": step.id,
                    "tool": step.tool,
                    "target": step.target,
                    "parameters": dict(step.parameters),
                    "risk": step.risk,
                    "requires_approval": step.requires_approval,
                    "state": step.state.value,
                    "rationale": step.rationale,
                }
                for step in plan.steps
            ],
        }

    @staticmethod
    def _plan_from_dict(data: dict[str, Any]) -> MissionPlan:
        steps = tuple(
            MissionStep(
                id=step["id"],
                tool=step["tool"],
                target=step["target"],
                parameters=step.get("parameters", {}),
                risk=int(step["risk"]),
                requires_approval=bool(step["requires_approval"]),
                state=StepState(step["state"]),
                rationale=step["rationale"],
            )
            for step in data["steps"]
        )
        return MissionPlan(id=data["id"], target=data["target"], steps=steps)

    @staticmethod
    def _run_to_dict(run: MissionRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "plan_id": run.plan_id,
            "target": run.target,
            "state": run.state.value,
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "steps": [
                {
                    "step_id": step.step_id,
                    "tool": step.tool,
                    "target": step.target,
                    "state": step.state.value,
                    "job_id": step.job_id,
                    "evidence_id": step.evidence_id,
                    "observation_id": step.observation_id,
                    "error": step.error,
                    "metadata": step.metadata,
                }
                for step in run.steps
            ],
            "observations": [
                {
                    "id": item.id,
                    "source": item.source,
                    "target": item.target,
                    "summary": item.summary,
                    "evidence_id": item.evidence_id,
                    "captured_at": item.captured_at.isoformat(),
                    "metadata": dict(item.metadata),
                }
                for item in run.observations
            ],
            "evidence": [
                {
                    "id": item.id,
                    "tool": item.tool,
                    "target": item.target,
                    "argv": list(item.argv),
                    "exit_code": item.exit_code,
                    "stdout": item.stdout,
                    "stderr": item.stderr,
                    "started_at": item.started_at.isoformat(),
                    "finished_at": item.finished_at.isoformat(),
                }
                for item in run.evidence
            ],
            "graph": {
                "nodes": [
                    {"id": node.id, "kind": node.kind, "label": node.label, "metadata": dict(node.metadata)}
                    for node in run.graph.nodes.values()
                ],
                "edges": [
                    {"source": edge.source, "relation": edge.relation, "target": edge.target}
                    for edge in run.graph.edges
                ],
            },
        }

    @staticmethod
    def _run_from_dict(data: dict[str, Any]) -> MissionRun:
        graph = EvidenceGraph()
        for node in data.get("graph", {}).get("nodes", []):
            graph.add_node(GraphNode(id=node["id"], kind=node["kind"], label=node["label"], metadata=node.get("metadata", {})))
        for edge in data.get("graph", {}).get("edges", []):
            graph.link(edge["source"], edge["relation"], edge["target"])
        return MissionRun(
            id=data["id"],
            plan_id=data["plan_id"],
            target=data["target"],
            state=MissionRunState(data["state"]),
            steps=[
                StepExecution(
                    step_id=step["step_id"],
                    tool=step["tool"],
                    target=step["target"],
                    state=StepExecutionState(step["state"]),
                    job_id=step.get("job_id"),
                    evidence_id=step.get("evidence_id"),
                    observation_id=step.get("observation_id"),
                    error=step.get("error"),
                    metadata=dict(step.get("metadata", {})),
                )
                for step in data["steps"]
            ],
            observations=[
                Observation(
                    id=item["id"],
                    source=item["source"],
                    target=item.get("target"),
                    summary=item["summary"],
                    evidence_id=item.get("evidence_id"),
                    captured_at=datetime.fromisoformat(item["captured_at"]),
                    metadata=dict(item.get("metadata", {})),
                )
                for item in data.get("observations", [])
            ],
            evidence=[
                EvidenceRecord(
                    id=item["id"],
                    tool=item["tool"],
                    target=item.get("target"),
                    argv=tuple(item["argv"]),
                    exit_code=int(item["exit_code"]),
                    stdout=item.get("stdout", ""),
                    stderr=item.get("stderr", ""),
                    started_at=datetime.fromisoformat(item["started_at"]),
                    finished_at=datetime.fromisoformat(item["finished_at"]),
                )
                for item in data.get("evidence", [])
            ],
            graph=graph,
            started_at=datetime.fromisoformat(data["started_at"]),
            finished_at=datetime.fromisoformat(data["finished_at"]) if data.get("finished_at") else None,
        )
