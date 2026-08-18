from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


@dataclass(frozen=True, slots=True)
class BinaryResolution:
    ready: bool
    path: str | None
    code: str
    detail: str
    candidates: tuple[str, ...] = ()
    rejected: tuple[str, ...] = ()


_HTTPX_REQUIRED_HELP_MARKERS = (
    "-silent",
    "-status-code",
    "-tech-detect",
    "-timeout",
)


def _candidate_names(name: str, environ: Mapping[str, str]) -> tuple[str, ...]:
    if os.name != "nt":
        return (name,)
    extensions = [item.strip().lower() for item in str(environ.get("PATHEXT", ".EXE;.BAT;.CMD")).split(";") if item.strip()]
    if Path(name).suffix:
        return (name,)
    return tuple(name + extension for extension in extensions)


def executable_candidates(name: str, *, environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Return executable PATH candidates in search order without trusting the first match."""
    env = os.environ if environ is None else environ
    seen: set[str] = set()
    ordered: list[str] = []
    for raw_directory in str(env.get("PATH", "")).split(os.pathsep):
        directory = Path(raw_directory or ".").expanduser()
        for candidate_name in _candidate_names(name, env):
            candidate = directory / candidate_name
            try:
                if not candidate.is_file() or not os.access(candidate, os.X_OK):
                    continue
                resolved = str(candidate.resolve())
            except OSError:
                continue
            if resolved not in seen:
                seen.add(resolved)
                ordered.append(resolved)
    return tuple(ordered)


def probe_projectdiscovery_httpx(
    path: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    timeout_seconds: float = 3.0,
) -> tuple[bool, str]:
    """Verify the CLI contract TONMEN actually depends on instead of trusting its filename."""
    try:
        completed = runner(
            [path, "-h"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"identity probe failed: {exc}"

    output = f"{completed.stdout or ''}\n{completed.stderr or ''}".lower()[:131_072]
    missing = tuple(marker for marker in _HTTPX_REQUIRED_HELP_MARKERS if marker not in output)
    if missing:
        return False, "missing required ProjectDiscovery httpx CLI flags: " + ", ".join(missing)
    return True, "compatible ProjectDiscovery httpx CLI contract"


def resolve_projectdiscovery_httpx(
    *,
    environ: Mapping[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> BinaryResolution:
    """Find the first PATH httpx candidate compatible with TONMEN's typed argv contract."""
    candidates = executable_candidates("httpx", environ=environ)
    if not candidates:
        return BinaryResolution(
            False,
            None,
            "missing_binary",
            "ProjectDiscovery httpx CLI is not available in PATH",
        )

    rejected: list[str] = []
    reasons: list[str] = []
    for candidate in candidates:
        compatible, reason = probe_projectdiscovery_httpx(candidate, runner=runner)
        if compatible:
            shadow_note = ""
            if rejected:
                shadow_note = f"; ignored incompatible earlier PATH candidate(s): {', '.join(rejected)}"
            return BinaryResolution(
                True,
                candidate,
                "ready",
                f"ProjectDiscovery httpx CLI ready: {candidate}{shadow_note}",
                candidates=candidates,
                rejected=tuple(rejected),
            )
        rejected.append(candidate)
        reasons.append(f"{candidate}: {reason}")

    return BinaryResolution(
        False,
        None,
        "wrong_binary_identity",
        "PATH contains httpx executable(s), but none satisfy the ProjectDiscovery CLI contract: " + "; ".join(reasons),
        candidates=candidates,
        rejected=tuple(rejected),
    )
