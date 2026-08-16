from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .core.config import TonmenConfig


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class DoctorReport:
    checks: tuple[DoctorCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.ok for check in self.checks if check.required)


def _workspace_check(config: TonmenConfig) -> DoctorCheck:
    probe: Path | None = None
    try:
        config.workspace.mkdir(parents=True, exist_ok=True)
        probe = config.workspace / ".tonmen-doctor-write"
        probe.write_text("ok\n", encoding="utf-8")
        return DoctorCheck("workspace", True, f"writable: {config.workspace}")
    except OSError as exc:
        return DoctorCheck("workspace", False, f"not writable: {config.workspace} ({exc})")
    finally:
        if probe is not None:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass


def run_doctor(
    config: TonmenConfig,
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> DoctorReport:
    checks: list[DoctorCheck] = []

    python_ok = sys.version_info >= (3, 10)
    checks.append(
        DoctorCheck(
            "python",
            python_ok,
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} "
            f"({'supported' if python_ok else 'requires >=3.10'})",
        )
    )

    if config.config_path and config.config_path.exists():
        checks.append(DoctorCheck("config", True, str(config.config_path), required=False))
    else:
        path = config.config_path or Path.cwd() / "tonmen.toml"
        checks.append(
            DoctorCheck(
                "config",
                True,
                f"defaults active; create {path} with `tonmen init`",
                required=False,
            )
        )

    checks.append(_workspace_check(config))

    for executable, note in (
        ("nmap", "Nmap network scanner"),
        ("httpx", "ProjectDiscovery HTTPx CLI (not the Python httpx package)"),
        ("nuclei", "ProjectDiscovery Nuclei CLI"),
    ):
        path = which(executable)
        checks.append(
            DoctorCheck(
                executable,
                path is not None,
                f"{note}: {path}" if path else f"{note}: not found in PATH",
            )
        )

    return DoctorReport(tuple(checks))


def render_doctor(report: DoctorReport) -> str:
    lines = ["天醫 Doctor"]
    for check in report.checks:
        marker = "OK" if check.ok else "MISS"
        optional = " (info)" if not check.required else ""
        lines.append(f"[{marker:<4}] {check.name:<10}{optional}  {check.detail}")
    lines.append("")
    lines.append("Ready for governed execution: " + ("YES" if report.ready else "NO"))
    return "\n".join(lines)
