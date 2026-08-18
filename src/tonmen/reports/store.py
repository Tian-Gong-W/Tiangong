from __future__ import annotations

import json
import os
from pathlib import Path

from tonmen.adaptive import assess_evidence_confidence
from tonmen.missions import MissionPlan, MissionRun

from .generator import build_report, render_markdown


def _confidence_payload(plan: MissionPlan, run: MissionRun) -> dict:
    assessment = assess_evidence_confidence(plan, run)
    claims = [
        {
            "key": item.key,
            "subject": item.subject,
            "assertion": item.assertion,
            "state": item.state.value,
            "confidence": item.confidence,
            "support_fact_ids": list(item.support_fact_ids),
            "conflict_fact_ids": list(item.conflict_fact_ids),
            "sources": list(item.sources),
            "observed_values": list(item.observed_values),
        }
        for item in assessment.claims
    ]
    return {
        "supported": len(assessment.supported),
        "conflicted": len(assessment.conflicted),
        "unresolved": len(assessment.unresolved),
        "conflict_fact_ids": list(assessment.conflict_fact_ids),
        "claims": claims,
    }


def _confidence_markdown(payload: dict) -> str:
    lines = [
        "## Evidence Confidence / Conflict",
        "",
        f"- Supported claims: {payload.get('supported', 0)}",
        f"- Conflicted claims: {payload.get('conflicted', 0)}",
        f"- Unresolved claims: {payload.get('unresolved', 0)}",
        "- Rule: absence of evidence is not treated as contradictory evidence.",
        "",
    ]
    claims = payload.get("claims", [])
    if not claims:
        lines.extend(["No confidence claims were derived.", ""])
        return "\n".join(lines)
    for claim in claims:
        lines.extend(
            [
                f"### {claim.get('subject') or claim.get('key')}",
                "",
                f"- State: **{claim.get('state', 'unresolved')}**",
                f"- Assertion: `{claim.get('assertion') or '—'}`",
                f"- Confidence: `{float(claim.get('confidence', 0.0)):.4f}`",
                f"- Sources: `{', '.join(claim.get('sources', [])) or '—'}`",
                f"- Observed values: `{', '.join(claim.get('observed_values', [])) or '—'}`",
                f"- Support Facts: `{', '.join(claim.get('support_fact_ids', [])) or '—'}`",
                f"- Conflict Facts: `{', '.join(claim.get('conflict_fact_ids', [])) or '—'}`",
                "",
            ]
        )
    return "\n".join(lines)


def _ai_payload(run: MissionRun) -> list[dict]:
    return [
        {
            "id": node.id,
            "kind": node.kind,
            "label": node.label,
            "metadata": dict(node.metadata),
        }
        for node in run.graph.nodes.values()
        if node.kind in {"ai.advisory", "ai.advisory_error"}
    ]


def _ai_markdown(items: list[dict]) -> str:
    lines = [
        "## Local AI Advisory",
        "",
        "- Optional local analysis only; deterministic TONMEN remains authoritative.",
        "- API key required by TONMEN: no",
        "- Execution authority: none",
        "",
    ]
    if not items:
        lines.extend(["No local AI advisory was recorded for this mission.", ""])
        return "\n".join(lines)
    for index, item in enumerate(items, start=1):
        metadata = item.get("metadata", {})
        if item.get("kind") == "ai.advisory_error":
            lines.extend(
                [
                    f"### Advisory {index}: deterministic fallback",
                    "",
                    f"- Provider/model: `{metadata.get('provider', '—')}` / `{metadata.get('model', '—')}`",
                    f"- Error: {metadata.get('error') or item.get('label') or '—'}",
                    f"- Fallback: `{metadata.get('fallback', 'deterministic')}`",
                    f"- Local only: `{metadata.get('local_only', True)}`",
                    f"- Execution authority: `{metadata.get('execution_authority', False)}`",
                    "",
                ]
            )
            continue
        hypotheses = metadata.get("hypotheses", [])
        lines.extend(
            [
                f"### Advisory {index}: {metadata.get('provider', 'local')} / {metadata.get('model', '—')}",
                "",
                f"- Summary: {metadata.get('summary') or item.get('label') or '—'}",
                f"- Focus: `{', '.join(metadata.get('focus', [])) or '—'}`",
                f"- Basis Facts: `{', '.join(metadata.get('basis_fact_ids', [])) or '—'}`",
                f"- Challenge decision: `{metadata.get('challenge_decision', False)}`",
                f"- Challenge reason: {metadata.get('challenge_reason') or '—'}",
                f"- Hypotheses: `{len(hypotheses)}`",
                f"- Local only: `{metadata.get('local_only', True)}`",
                f"- API key required: `{metadata.get('api_key_required', False)}`",
                f"- Execution authority: `{metadata.get('execution_authority', False)}`",
                "",
            ]
        )
    return "\n".join(lines)


class ReportStore:
    def __init__(self, workspace: Path) -> None:
        self.root = Path(workspace) / "reports"

    @staticmethod
    def _validate_run_id(run_id: str) -> str:
        value = run_id.strip().lower()
        if len(value) != 32 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("invalid mission run id")
        return value

    def _ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    def _path(self, run_id: str, suffix: str) -> Path:
        return self.root / f"{self._validate_run_id(run_id)}.{suffix}"

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary = path.with_name(f".{path.name}.tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def save(self, plan: MissionPlan, run: MissionRun) -> dict:
        if run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")
        self._ensure_root()
        report = build_report(plan, run)
        confidence = _confidence_payload(plan, run)
        ai_advisories = _ai_payload(run)
        report["evidence_confidence"] = confidence
        report["ai_advisories"] = ai_advisories
        report.setdefault("summary", {})["supported_claims"] = confidence["supported"]
        report["summary"]["conflicted_claims"] = confidence["conflicted"]
        report["summary"]["unresolved_claims"] = confidence["unresolved"]
        report["summary"]["ai_advisories"] = sum(1 for item in ai_advisories if item["kind"] == "ai.advisory")
        report["summary"]["ai_advisory_errors"] = sum(1 for item in ai_advisories if item["kind"] == "ai.advisory_error")
        self._atomic_write(
            self._path(run.id, "json"),
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
        markdown = (
            render_markdown(report).rstrip()
            + "\n\n"
            + _confidence_markdown(confidence).rstrip()
            + "\n\n"
            + _ai_markdown(ai_advisories).rstrip()
            + "\n"
        )
        self._atomic_write(self._path(run.id, "md"), markdown)
        return report

    def load_json(self, run_id: str) -> dict:
        return json.loads(self._path(run_id, "json").read_text(encoding="utf-8"))

    def load_markdown(self, run_id: str) -> str:
        return self._path(run_id, "md").read_text(encoding="utf-8")

    def delete(self, run_id: str) -> bool:
        removed = False
        for suffix in ("json", "md"):
            path = self._path(run_id, suffix)
            try:
                path.unlink()
                removed = True
            except FileNotFoundError:
                pass
        return removed
