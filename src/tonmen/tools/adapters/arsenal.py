from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from tonmen.tools.base import CostEstimate, RiskLevel, ToolAdapter, ToolReadiness, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_host_target, validate_web_target


DEFAULT_ARSENAL_ROOT = Path("/home/wang/真心")


class ArsenalSqliAdapter(ToolAdapter):
    """Offensive SQL injection detector from the specialized offensive arsenal."""

    spec = ToolSpec(
        name="arsenal.sqli",
        category="web.exploit",
        description="Arsenal SQLi detector testing error-based, boolean-blind, time-blind and WAF evasion variants",
        risk=RiskLevel.ACTIVE,
        capabilities=("vulnerability.detect", "sqli.exploit", "waf.bypass"),
        accepts=("url",),
        produces=("vulnerability_finding", "injection_point"),
        modalities=("http", "text"),
        estimated_cost=CostEstimate(wall_seconds=15, network_requests=30),
        replayable=True,
        isolation_profile="scoped_network",
        default_parameters=(("params", ""), ("method", "GET")),
    )

    def __init__(self, script_path: Path | None = None) -> None:
        self.script_path = (
            script_path
            or DEFAULT_ARSENAL_ROOT / ".dsh" / "skills" / "sql-injection" / "scripts" / "sqli_detector.py"
        )

    def readiness(self) -> ToolReadiness:
        if self.script_path.is_file():
            return ToolReadiness(True, "ready", f"arsenal script ready: {self.script_path}")
        return ToolReadiness(
            False,
            "missing_script",
            f"arsenal sqli script not found at {self.script_path}",
            remediation="Ensure the arsenal path is mounted at /home/wang/真心",
        )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"params", "method"})
        validate_web_target(request.target)

    def build_argv(self, request: ToolRequest) -> Sequence[str]:
        self.validate(request)
        argv = [sys.executable, str(self.script_path), "-u", str(request.target)]
        params = request.parameters.get("params")
        if params:
            argv.extend(["-p", str(params)])
        method = request.parameters.get("method", "GET").upper()
        if method in {"GET", "POST"}:
            argv.extend(["--method", method])
        return tuple(argv)


class ArsenalPortscanAdapter(ToolAdapter):
    """High-concurrency async port scanner with service banner identification."""

    spec = ToolSpec(
        name="arsenal.portscan",
        category="network.recon",
        description="Arsenal high-speed async port scanner with service banner identification",
        risk=RiskLevel.DISCOVERY,
        capabilities=("port.scan", "service.fingerprint", "banner.grab"),
        accepts=("host",),
        produces=("open_ports", "service_banners"),
        modalities=("tcp", "text"),
        estimated_cost=CostEstimate(wall_seconds=10, network_requests=50),
        replayable=True,
        isolation_profile="scoped_network",
        default_parameters=(("ports", "1-1000"), ("banner", True)),
    )

    def __init__(self, script_path: Path | None = None) -> None:
        self.script_path = (
            script_path
            or DEFAULT_ARSENAL_ROOT / ".dsh" / "skills" / "port-and-service-scan" / "scripts" / "port_scanner.py"
        )

    def readiness(self) -> ToolReadiness:
        if self.script_path.is_file():
            return ToolReadiness(True, "ready", f"arsenal script ready: {self.script_path}")
        return ToolReadiness(
            False,
            "missing_script",
            f"arsenal port scanner script not found at {self.script_path}",
        )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"ports", "banner"})
        validate_host_target(request.target)

    def build_argv(self, request: ToolRequest) -> Sequence[str]:
        self.validate(request)
        argv = [sys.executable, str(self.script_path), "-t", str(request.target)]
        ports = request.parameters.get("ports", "1-1000")
        argv.extend(["-p", str(ports)])
        if request.parameters.get("banner", True):
            argv.append("--banner")
        return tuple(argv)


class ArsenalWafAdapter(ToolAdapter):
    """Arsenal WAF & CDN fingerprinting adapter."""

    spec = ToolSpec(
        name="arsenal.waf",
        category="web.fingerprint",
        description="Arsenal WAF and CDN signature detector",
        risk=RiskLevel.PASSIVE,
        capabilities=("waf.detect", "cdn.fingerprint"),
        accepts=("url", "host"),
        produces=("waf_signature", "cdn_provider"),
        modalities=("http", "text"),
        estimated_cost=CostEstimate(wall_seconds=5, network_requests=5),
        replayable=True,
        isolation_profile="scoped_network",
        default_parameters=(),
    )

    def __init__(self, script_path: Path | None = None) -> None:
        self.script_path = (
            script_path
            or DEFAULT_ARSENAL_ROOT / ".dsh" / "skills" / "waf-and-cdn-detection" / "scripts" / "script.py"
        )

    def readiness(self) -> ToolReadiness:
        if self.script_path.is_file():
            return ToolReadiness(True, "ready", f"arsenal script ready: {self.script_path}")
        return ToolReadiness(
            False,
            "missing_script",
            f"arsenal WAF script not found at {self.script_path}",
        )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, set())
        validate_web_target(request.target)

    def build_argv(self, request: ToolRequest) -> Sequence[str]:
        self.validate(request)
        return (sys.executable, str(self.script_path), "-t", str(request.target))


class SqlmapAdapter(ToolAdapter):
    """System-level sqlmap automation adapter."""

    spec = ToolSpec(
        name="sqlmap",
        category="web.exploit",
        description="Automatic SQL injection detection and database takeover tool",
        risk=RiskLevel.ACTIVE,
        capabilities=("vulnerability.detect", "sqli.exploit", "database.dump"),
        accepts=("url",),
        produces=("vulnerability_finding", "db_enumeration"),
        modalities=("http", "text"),
        estimated_cost=CostEstimate(wall_seconds=25, network_requests=60),
        replayable=True,
        isolation_profile="scoped_network",
        default_parameters=(("batch", True), ("level", 1), ("risk", 1)),
    )

    def readiness(self) -> ToolReadiness:
        path = shutil.which("sqlmap")
        if path:
            return ToolReadiness(True, "ready", f"sqlmap ready: {path}", metadata={"path": path})
        return ToolReadiness(
            False,
            "missing_binary",
            "sqlmap is not available in PATH",
            remediation="Install sqlmap: apt-get install sqlmap",
        )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"batch", "level", "risk"})
        validate_web_target(request.target)

    def build_argv(self, request: ToolRequest) -> Sequence[str]:
        self.validate(request)
        argv = [
            "sqlmap",
            "-u", str(request.target),
            "--batch",
            "--random-agent",
            "--smart",
        ]
        level = request.parameters.get("level", 1)
        risk = request.parameters.get("risk", 1)
        argv.extend(["--level", str(level), "--risk", str(risk)])
        return tuple(argv)
