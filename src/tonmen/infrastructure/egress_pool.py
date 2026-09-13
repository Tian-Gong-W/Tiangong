from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EgressNode:
    id: str
    proxy_url: str
    region: str = "auto"
    healthy: bool = True
    cooldown_until: float = 0.0
    failure_count: int = 0
    total_requests: int = 0

    @property
    def is_available(self) -> bool:
        if not self.healthy:
            return False
        return time.time() >= self.cooldown_until


class EgressManager:
    """Manages egress nodes and proxy routing with dual-mode dispatch:

    1. Stateless Round-Robin for high-frequency discovery
    2. Sticky Session Routing for authenticated exploit and session maintenance
    3. Auto-cooldown circuit breaker on 429 Too Many Requests or 403 blocks
    """

    def __init__(self, default_cooldown_seconds: int = 1800) -> None:
        self.nodes: Dict[str, EgressNode] = {}
        self.sticky_bindings: Dict[str, str] = {}  # domain -> node_id
        self.round_robin_idx: int = 0
        self.default_cooldown_seconds = default_cooldown_seconds

    def add_node(self, node_id: str, proxy_url: str, region: str = "auto") -> None:
        self.nodes[node_id] = EgressNode(id=node_id, proxy_url=proxy_url, region=region)

    def get_stateless_proxy(self) -> Optional[str]:
        """Round-robin through available healthy nodes."""
        available = [n for n in self.nodes.values() if n.is_available]
        if not available:
            return None
        self.round_robin_idx = (self.round_robin_idx + 1) % len(available)
        node = available[self.round_robin_idx]
        node.total_requests += 1
        return node.proxy_url

    def get_sticky_proxy(self, target_domain: str) -> Optional[str]:
        """Consistently binds a target domain to a single healthy proxy node to avoid session invalidation."""
        domain_key = target_domain.strip().lower()

        # Check existing binding
        bound_id = self.sticky_bindings.get(domain_key)
        if bound_id and bound_id in self.nodes and self.nodes[bound_id].is_available:
            self.nodes[bound_id].total_requests += 1
            return self.nodes[bound_id].proxy_url

        # Select new consistent node using hash
        available = [n for n in self.nodes.values() if n.is_available]
        if not available:
            return None

        hash_val = int(hashlib.md5(domain_key.encode("utf-8")).hexdigest(), 16)
        chosen_node = available[hash_val % len(available)]
        self.sticky_bindings[domain_key] = chosen_node.id
        chosen_node.total_requests += 1
        return chosen_node.proxy_url

    def report_response(self, proxy_url: str, status_code: int) -> None:
        """Evaluates feedback from target; isolates node on 429 or 403."""
        matching_nodes = [n for n in self.nodes.values() if n.proxy_url == proxy_url]
        if not matching_nodes:
            return

        node = matching_nodes[0]
        if status_code in (429, 403):
            node.failure_count += 1
            node.cooldown_until = time.time() + self.default_cooldown_seconds
            # Evict sticky bindings that pointed to this cooled down node
            for domain, nid in list(self.sticky_bindings.items()):
                if nid == node.id:
                    del self.sticky_bindings[domain]
        elif status_code < 400:
            node.failure_count = max(0, node.failure_count - 1)

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_nodes": len(self.nodes),
            "healthy_nodes": len([n for n in self.nodes.values() if n.is_available]),
            "cooldown_nodes": len([n for n in self.nodes.values() if not n.is_available and n.healthy]),
            "sticky_domains_count": len(self.sticky_bindings),
        }
