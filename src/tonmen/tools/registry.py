from __future__ import annotations

from collections.abc import Iterator

from .base import ToolAdapter


class ToolRegistry:
    """Single source of truth for tool capabilities exposed to agents."""

    def __init__(self) -> None:
        self._adapters: dict[str, ToolAdapter] = {}

    def register(self, adapter: ToolAdapter) -> None:
        name = adapter.spec.name.strip().lower()
        if not name:
            raise ValueError("tool name cannot be empty")
        if name in self._adapters:
            raise ValueError(f"tool already registered: {name}")
        self._adapters[name] = adapter

    def get(self, name: str) -> ToolAdapter:
        key = name.strip().lower()
        try:
            return self._adapters[key]
        except KeyError as exc:
            raise KeyError(f"unknown TONMEN tool: {name}") from exc

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name.strip().lower() in self._adapters

    def __len__(self) -> int:
        return len(self._adapters)

    def __iter__(self) -> Iterator[ToolAdapter]:
        return iter(self._adapters.values())
