from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class LiveSecurityKnowledgeHub:
    """Real-time Security Knowledge Hub (RAG Engine).

    Uses SQLite FTS5 full-text indexing to store Tactical Knowledge Objects (TKOs).
    Injects up-to-date vulnerability heuristics and bypass tactics into older LLM context windows.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            data_dir = Path.home() / ".tonmen" / "knowledge"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "live_knowledge_hub.db")
        else:
            self.db_path = db_path

        self._init_db()
        self._seed_default_tactics()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id TEXT PRIMARY KEY,
                    component TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    cve_id TEXT,
                    prerequisites TEXT,
                    bypass_tactics TEXT,
                    payload_template TEXT,
                    created_at REAL
                )
                """
            )
            # FTS5 Virtual table for fast BM25 matching
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    id UNINDEXED,
                    component,
                    category,
                    title,
                    prerequisites,
                    bypass_tactics,
                    content='knowledge_items',
                    content_rowid='rowid'
                )
                """
            )
            conn.commit()

    def store_tko(
        self,
        item_id: str,
        component: str,
        category: str,
        title: str,
        cve_id: Optional[str] = None,
        prerequisites: str = "",
        bypass_tactics: str = "",
        payload_template: str = "",
    ) -> None:
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_items (
                    id, component, category, title, cve_id, prerequisites, bypass_tactics, payload_template, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (item_id, component, category, title, cve_id or "", prerequisites, bypass_tactics, payload_template, now),
            )
            # Update FTS
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_fts (rowid, id, component, category, title, prerequisites, bypass_tactics)
                VALUES (
                    (SELECT rowid FROM knowledge_items WHERE id = ?),
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (item_id, item_id, component, category, title, prerequisites, bypass_tactics),
            )
            conn.commit()

    def query_context(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Hybrid BM25 search matching component, fingerprint, or vulnerability pattern."""
        cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
        if not cleaned:
            return []

        tokens = [t for t in cleaned.split() if len(t) > 1][:8]
        if not tokens:
            return []

        match_clause = " OR ".join(f'"{t}"*' for t in tokens)

        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    """
                    SELECT k.id, k.component, k.category, k.title, k.cve_id, k.prerequisites, k.bypass_tactics, k.payload_template
                    FROM knowledge_fts f
                    JOIN knowledge_items k ON f.id = k.id
                    WHERE knowledge_fts MATCH ?
                    ORDER BY bm25(knowledge_fts)
                    LIMIT ?
                    """,
                    (match_clause, limit),
                )
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
        except Exception:
            # Fallback simple LIKE search if FTS query syntax errors
            with self._get_conn() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, component, category, title, cve_id, prerequisites, bypass_tactics, payload_template
                    FROM knowledge_items
                    WHERE component LIKE ? OR title LIKE ?
                    LIMIT ?
                    """,
                    (f"%{tokens[0]}%", f"%{tokens[0]}%", limit),
                )
                return [dict(r) for r in cursor.fetchall()]

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Convenience alias for query_context."""
        return self.query_context(query, limit=top_k)

    def count(self) -> int:
        """Returns total count of stored tactical knowledge objects."""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT count(*) FROM knowledge_items")
            row = cursor.fetchone()
            return row[0] if row else 0

    def format_context_for_prompt(self, observed_fingerprints: List[str]) -> str:
        """Formats matched security advisories and bypass rules into LLM system context."""
        all_results: Dict[str, Dict[str, Any]] = {}
        for fp in observed_fingerprints[:5]:
            for item in self.query_context(fp, limit=3):
                all_results[item["id"]] = item

        if not all_results:
            return ""

        lines = ["\n[LIVE SECURITY KNOWLEDGE INJECTION]:"]
        for idx, item in enumerate(all_results.values(), 1):
            cve = f" ({item['cve_id']})" if item.get("cve_id") else ""
            lines.append(f"{idx}. [{item['component']}] {item['title']}{cve}")
            if item.get("prerequisites"):
                lines.append(f"   - Prerequisites: {item['prerequisites']}")
            if item.get("bypass_tactics"):
                lines.append(f"   - Modern Bypass / Verification: {item['bypass_tactics']}")
        return "\n".join(lines)

    def _seed_default_tactics(self) -> None:
        """Pre-populates cutting-edge security advisories & modern bypass heuristics."""
        seeds = [
            (
                "tko-waf-chunked",
                "WAF / Reverse Proxy",
                "Evasion",
                "HTTP/1.1 Chunked Transfer-Encoding Smuggling & Normalization Evasion",
                "CVE-2023-25690",
                "Reverse proxy in front of backend server; hop-by-hop header parsing asymmetry",
                "Send Transfer-Encoding: chunked with obtrusive space or newline characters to cause pipeline desync",
                "POST / HTTP/1.1\\r\\nTransfer-Encoding: chunked\\r\\n\\r\\n0\\r\\n\\r\\n",
            ),
            (
                "tko-spring-boot-actuator",
                "Spring Boot",
                "Framework",
                "Spring Boot 3.x Actuator Heapdump & Env Leakage to RCE",
                "CVE-2022-22965",
                "Actuator endpoints exposed (/actuator/env, /actuator/heapdump, /actuator/gateway)",
                "Probe /actuator/env for masked database/JWT credentials; check gateway dynamic routes for SpEL injection",
                "/actuator/gateway/routes",
            ),
            (
                "tko-jwt-none-alg",
                "JWT",
                "Authentication",
                "JWT Alg Confusion (RS256 to HS256 with Public Key Verification)",
                "CVE-2024-jwt-conf",
                "JWT using asymmetric signing; public key is discoverable via /.well-known/jwks.json",
                "Change header alg to HS256, HMAC-SHA256 sign using the retrieved PEM-encoded public key as secret",
                "{\"alg\":\"HS256\",\"typ\":\"JWT\"}",
            ),
            (
                "tko-path-traversal-normalize",
                "Nginx / Tomcat",
                "Path Traversal",
                "Reverse Proxy Path Normalization Bypass (/..;/ and /%2e%2e/)",
                "CVE-2023-path-norm",
                "Nginx location block matching with upstream pass without trailing slash",
                "Use /..;/ or URL-encoded dots to bypass restricted location prefix while Tomcat resolves parent path",
                "/admin/..;/dashboard",
            ),
        ]
        for s in seeds:
            self.store_tko(s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7])
