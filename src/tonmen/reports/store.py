from __future__ import annotations

import json
import os
from pathlib import Path

from tonmen.missions import MissionPlan, MissionRun

from .generator import build_report, render_markdown


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
        self._atomic_write(
            self._path(run.id, "json"),
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
        self._atomic_write(self._path(run.id, "md"), render_markdown(report))
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
