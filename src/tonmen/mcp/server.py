from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tonmen.tools import ToolRequest
from tonmen.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from tonmen.core.runtime import TonmenRuntime


def catalog(registry: ToolRegistry) -> list[dict[str, Any]]:
    return [
        {
            "name": adapter.spec.name,
            "category": adapter.spec.category,
            "description": adapter.spec.description,
            "risk": int(adapter.spec.risk),
            "capabilities": list(adapter.spec.capabilities),
        }
        for adapter in registry
    ]


def guarded_submit(
    runtime: "TonmenRuntime",
    *,
    tool: str,
    target: str,
    parameters: dict[str, Any] | None = None,
    approval_token: str | None = None,
) -> dict[str, Any]:
    """Transport-neutral MCP execution boundary; never issues its own approvals."""
    if runtime.jobs is None:
        raise RuntimeError("TONMEN guarded runtime is not initialized")
    job = runtime.jobs.submit(
        ToolRequest(tool=tool, target=target, parameters=parameters or {}),
        approval_token=approval_token,
    )
    return {
        "job_id": job.id,
        "status": job.status.value,
        "error": job.error,
        "evidence_id": job.outcome.evidence.id if job.outcome else None,
    }


def create_fastmcp_server(runtime: "TonmenRuntime"):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install TONMEN with the 'mcp' extra to enable MCP") from exc

    server = FastMCP("TONMEN")

    @server.tool()
    def tonmen_catalog() -> list[dict[str, Any]]:
        return catalog(runtime.registry)

    @server.tool()
    def tonmen_submit(
        tool: str,
        target: str,
        parameters: dict[str, Any] | None = None,
        approval_token: str | None = None,
    ) -> dict[str, Any]:
        """Submit a scoped request. Approval grants must come from the local control plane."""
        return guarded_submit(
            runtime,
            tool=tool,
            target=target,
            parameters=parameters,
            approval_token=approval_token,
        )

    return server
