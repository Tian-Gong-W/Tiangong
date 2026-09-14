import asyncio
import os
import tempfile
from tonmen.infrastructure import (
    LiveSecurityKnowledgeHub,
    EgressManager,
    SessionVault,
)


def test_live_security_knowledge_hub():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_kh.db")
        hub = LiveSecurityKnowledgeHub(db_path=db_path)

        # Query Spring Boot
        results = hub.query_context("Spring Boot Actuator", limit=2)
        assert len(results) > 0
        assert "Spring Boot" in results[0]["component"]

        # Context formatting
        context = hub.format_context_for_prompt(["Spring Boot", "Nginx"])
        assert "LIVE SECURITY KNOWLEDGE INJECTION" in context
        assert "CVE-" in context


def test_egress_manager_routing_and_cooldown():
    em = EgressManager(default_cooldown_seconds=60)
    em.add_node("node-1", "http://proxy1:8080")
    em.add_node("node-2", "http://proxy2:8080")

    # Stateless round-robin
    p1 = em.get_stateless_proxy()
    p2 = em.get_stateless_proxy()
    assert p1 in ("http://proxy1:8080", "http://proxy2:8080")
    assert p2 in ("http://proxy1:8080", "http://proxy2:8080")

    # Sticky domain routing
    s1 = em.get_sticky_proxy("target.com")
    s2 = em.get_sticky_proxy("target.com")
    assert s1 == s2  # Consistent binding to same node!

    # Cooldown on 429
    em.report_response(s1, 429)
    status = em.get_status()
    assert status["cooldown_nodes"] == 1


def test_session_vault_lifecycle():
    async def run_async():
        vault = SessionVault(heartbeat_interval_seconds=1)

        # Store short-lived token (10 seconds)
        refreshed = False

        async def dummy_refresh(old_payload):
            nonlocal refreshed
            refreshed = True
            return {"token": "new_jwt_token"}

        vault.store_credential(
            cred_id="jwt-1",
            target_domain="auth.corp.com",
            cred_type="jwt",
            payload={"token": "old_jwt_token"},
            ttl_seconds=2,  # 2 seconds TTL
            keepalive_url="http://auth.corp.com/ping",
            refresh_callback=dummy_refresh,
        )

        cred = vault.get_credential("jwt-1")
        assert cred["token"] == "old_jwt_token"

        # Check maintenance pass
        await asyncio.sleep(1.7)  # More than 80% of 2s elapsed
        res = await vault.check_and_maintain()
        assert refreshed is True
        assert vault.get_credential("jwt-1")["token"] == "new_jwt_token"

    asyncio.run(run_async())
