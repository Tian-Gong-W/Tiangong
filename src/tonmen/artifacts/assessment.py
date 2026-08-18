from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

_MAX_SIGNALS = 128
_RISKY_IMPORTS = {
    "gets": ("unsafe_input_api", "Unbounded input API is linked; review callers and reachable input paths."),
    "strcpy": ("unsafe_copy_api", "Unbounded string copy API is linked; review destination sizing and callers."),
    "strcat": ("unsafe_concat_api", "Unbounded string concatenation API is linked; review destination sizing and callers."),
    "sprintf": ("unsafe_format_api", "Unbounded formatted-output API is linked; review destination sizing and format sources."),
    "vsprintf": ("unsafe_format_api", "Unbounded formatted-output API is linked; review destination sizing and format sources."),
    "scanf": ("input_parsing_api", "Formatted input API is linked; review width constraints and destination types."),
    "sscanf": ("input_parsing_api", "Formatted input API is linked; review width constraints and destination types."),
    "memcpy": ("raw_memory_copy_api", "Raw memory copy API is linked; review whether lengths are evidence-backed and bounded."),
    "memmove": ("raw_memory_copy_api", "Raw memory move API is linked; review whether lengths are evidence-backed and bounded."),
}


@dataclass(frozen=True, slots=True)
class ArtifactSignal:
    code: str
    title: str
    severity: str
    confidence: float
    category: str
    basis: tuple[str, ...]
    review: str
    vulnerability_confirmed: bool = False
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["basis"] = list(self.basis)
        return payload


def _symbol_names(linkage: Mapping[str, Any]) -> list[str]:
    imports = linkage.get("imports")
    if not isinstance(imports, list):
        return []
    names: list[str] = []
    for item in imports:
        if isinstance(item, str):
            names.append(item)
            continue
        if not isinstance(item, Mapping):
            continue
        library = str(item.get("library") or "")
        symbols = item.get("symbols")
        if not isinstance(symbols, list):
            continue
        for symbol in symbols:
            value = str(symbol or "")
            if value:
                names.append(f"{library}!{value}" if library else value)
    return names


def _plain_symbol(value: str) -> str:
    symbol = value.rsplit("!", 1)[-1]
    symbol = symbol.split("@", 1)[0]
    while symbol.startswith("_"):
        symbol = symbol[1:]
    return symbol.lower()


def assess_artifact(report: Mapping[str, Any]) -> dict[str, Any]:
    """Derive bounded review signals from static metadata only.

    Signals are hypotheses for human/static follow-up. They never claim code is
    exploitable merely because a mitigation is absent or a risky API is imported.
    """
    signals: list[ArtifactSignal] = []

    def add(signal: ArtifactSignal) -> None:
        if len(signals) < _MAX_SIGNALS:
            signals.append(signal)

    fmt = str(report.get("format") or "unknown").lower()
    mitigations = report.get("mitigations") if isinstance(report.get("mitigations"), Mapping) else {}

    mitigation_rules = {
        "elf": {
            "nx_stack": ("medium", "Executable stack metadata observed", "Review whether executable stack is required and whether stack-resident data can become control-flow relevant."),
            "pie_candidate": ("low", "Position-independent executable posture not observed", "Confirm final link type and ASLR behavior before assigning exploitability impact."),
            "gnu_relro": ("low", "GNU RELRO segment not observed", "Review relocation protection and writable control-flow-relevant tables."),
        },
        "pe": {
            "nx_compat": ("medium", "PE NX compatibility flag not observed", "Confirm runtime DEP policy and review executable-data exposure."),
            "aslr": ("low", "PE ASLR flag not observed", "Confirm image relocation behavior and deployment ASLR policy."),
            "control_flow_guard": ("info", "PE Control Flow Guard flag not observed", "Treat as defense-in-depth posture; do not infer a vulnerability from the flag alone."),
        },
        "macho": {
            "pie": ("low", "Mach-O PIE flag not observed", "Confirm load-address randomization behavior before assigning exploitability impact."),
        },
    }
    for key, (severity, title, review) in mitigation_rules.get(fmt, {}).items():
        if mitigations.get(key) is not False:
            continue
        add(
            ArtifactSignal(
                code=f"mitigation.{key}.absent",
                title=title,
                severity=severity,
                confidence=0.9,
                category="mitigation_posture",
                basis=(f"mitigations.{key}=false",),
                review=review,
            )
        )

    structure = report.get("structure") if isinstance(report.get("structure"), Mapping) else {}
    for kind in ("segments", "sections"):
        entries = structure.get(kind)
        if not isinstance(entries, list):
            continue
        for entry in entries[:256]:
            if not isinstance(entry, Mapping):
                continue
            permissions = str(entry.get("permissions") or "").upper()
            if "W" not in permissions or "X" not in permissions:
                continue
            name = str(entry.get("name") or kind[:-1] or "region")[:128]
            add(
                ArtifactSignal(
                    code=f"memory.{kind[:-1]}.writable_executable",
                    title=f"Writable + executable {kind[:-1]} metadata: {name}",
                    severity="medium",
                    confidence=0.95,
                    category="memory_permissions",
                    basis=(f"{kind}.{name}.permissions={permissions}",),
                    review="Determine why the region needs both write and execute permissions and whether build-time W^X hardening is possible.",
                )
            )

    linkage = report.get("linkage") if isinstance(report.get("linkage"), Mapping) else {}
    seen_api: set[str] = set()
    for symbol in _symbol_names(linkage)[:2048]:
        plain = _plain_symbol(symbol)
        rule = _RISKY_IMPORTS.get(plain)
        if rule is None or plain in seen_api:
            continue
        seen_api.add(plain)
        code, review = rule
        add(
            ArtifactSignal(
                code=f"api.{code}.{plain}",
                title=f"Review-sensitive imported API: {plain}",
                severity="info",
                confidence=0.8,
                category="linked_api_review",
                basis=(f"import={symbol}",),
                review=review,
            )
        )

    counts = {"info": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}
    for signal in signals:
        counts[signal.severity] = counts.get(signal.severity, 0) + 1

    review_plan: list[str] = []
    if any(signal.category == "memory_permissions" for signal in signals):
        review_plan.append("Correlate writable+executable regions with linker/build configuration and documented runtime requirements.")
    if any(signal.category == "linked_api_review" for signal in signals):
        review_plan.append("Locate callers of review-sensitive imports and trace bounds/data-flow statically before drawing a vulnerability conclusion.")
    if any(signal.category == "mitigation_posture" for signal in signals):
        review_plan.append("Confirm mitigation observations with format-aware metadata and deployment policy; absent metadata alone is not exploit proof.")
    if not review_plan:
        review_plan.append("Continue format-aware static review only if additional evidence justifies deeper analysis.")

    return {
        "mode": "static-report-only",
        "signals": [signal.as_dict() for signal in signals],
        "summary": {"signals": len(signals), "by_severity": counts},
        "review_plan": review_plan,
        "vulnerability_confirmed": False,
        "execution_authority": False,
        "payload_generated": False,
        "artifact_executed": False,
    }
