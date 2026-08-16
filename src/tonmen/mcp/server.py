from __future__ import annotations

from typing import Any

from tonmen.tools.registry import ToolRegistry


def catalog(registry: ToolRegistry) -> list[dict[str, Any]]:
    """Return a transport-neutral catalog suitable for an MCP boundary."""
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


def create_fastmcp_server(registry: ToolRegistry):
    """Create the optional FastMCP surface without making it a core dependency."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - optional integration
        raise RuntimeError("Install TONMEN with the 'mcp' extra to enable MCP") from exc

    server = FastMCP("TONMEN")

    @server.tool()
    def tonmen_catalog() -> list[dict[str, Any]]:
        """List capabilities registered in TONMEN."""
        return catalog(registry)

    return server
