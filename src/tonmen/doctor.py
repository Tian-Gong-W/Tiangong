from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

from .core.config import TonmenConfig


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    required: bool = True
    code: str = "ready"
    remediation: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


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
        return DoctorCheck(
            "workspace",
            False,
            f"not writable: {config.workspace} ({exc})",
            code="workspace_unwritable",
        )
    finally:
        if probe is not None:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass


def _has_nuclei_templates(root: Path) -> bool:
    if not root.is_dir():
        return False
    try:
        for pattern in ("*.yaml", "*.yml"):
            if next(root.rglob(pattern), None) is not None:
                return True
    except OSError:
        return False
    return False


def _nuclei_templates_check(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> DoctorCheck:
    env = os.environ if environ is None else environ
    configured = str(env.get("TONMEN_NUCLEI_TEMPLATES", "")).strip()
    root = Path(configured).expanduser() if configured else (home or Path.home()) / "nuclei-templates"
    root = root.resolve()
    if _has_nuclei_templates(root):
        return DoctorCheck(
            "nuclei-templates",
            True,
            f"templates ready: {root}",
            metadata={"path": str(root)},
        )
    return DoctorCheck(
        "nuclei-templates",
        False,
        f"no Nuclei YAML templates found under {root}",
        code="missing_templates",
        remediation=(
            "Run `nuclei -ut` to install/update community templates, then refresh Doctor. "
            "If templates live elsewhere, set TONMEN_NUCLEI_TEMPLATES to that directory."
        ),
        metadata={"path": str(root)},
    )


def run_doctor(
    config: TonmenConfig,
    *,
    which: Callable[[str], str | None] = shutil.which,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> DoctorReport:
    checks: list[DoctorCheck] = []

    python_ok = sys.version_info >= (3, 10)
    checks.append(
        DoctorCheck(
            "python",
            python_ok,
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} "
            f"({'supported' if python_ok else 'requires >=3.10'})",
            code="ready" if python_ok else "unsupported_python",
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
                code="ready" if path else "missing_binary",
                remediation=None if path else f"Install {executable} and make sure it is available in PATH.",
                metadata={"path": path} if path else {},
            )
        )

    nuclei_binary = next(check for check in checks if check.name == "nuclei")
    template_check = _nuclei_templates_check(environ=environ, home=home)
    if not nuclei_binary.ok:
        template_check = DoctorCheck(
            "nuclei-templates",
            False,
            "Nuclei templates cannot be validated until the nuclei binary is installed.",
            code="blocked_by_binary",
            remediation=nuclei_binary.remediation,
            metadata=template_check.metadata,
        )
    checks.append(template_check)

    return DoctorReport(tuple(checks))


def render_doctor(report: DoctorReport) -> str:
    lines = ["天醫 Doctor"]
    for check in report.checks:
        marker = "OK" if check.ok else "MISS"
        optional = " (info)" if not check.required else ""
        lines.append(f"[{marker:<4}] {check.name:<16}{optional}  {check.detail}")
        if check.remediation and not check.ok:
            lines.append(f"       fix: {check.remediation}")
    lines.append("")
    lines.append("Ready for governed execution: " + ("YES" if report.ready else "NO"))
    return "\n".join(lines)
