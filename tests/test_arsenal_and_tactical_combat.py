from __future__ import annotations

import sys
from pathlib import Path

from tonmen.arena import (
    ArenaLedger,
    ProbabilisticAttackGraph,
    TacticalCombatResult,
    TheArbiter,
    MissionArenaBridge,
)
from tonmen.infrastructure import LiveSecurityKnowledgeHub
from tonmen.tools.adapters import (
    ArsenalPortscanAdapter,
    ArsenalSqliAdapter,
    ArsenalWafAdapter,
    SqlmapAdapter,
    register_builtin_adapters,
)
from tonmen.tools.base import ToolRequest
from tonmen.tools.registry import ToolRegistry
from tonmen.evidence import EvidenceRecord
from tonmen.missions import MissionRun, MissionRunState


def test_arsenal_adapters_and_registry():
    registry = ToolRegistry()
    register_builtin_adapters(registry)

    # 1. Verify all expected tools registered
    assert "arsenal.portscan" in registry
    assert "arsenal.sqli" in registry
    assert "arsenal.waf" in registry
    assert "sqlmap" in registry
    assert "katana" in registry
    assert "subfinder" in registry

    # 2. Test Arsenal Portscan
    portscan = registry.get("arsenal.portscan")
    req_ps = ToolRequest(tool="arsenal.portscan", target="127.0.0.1", parameters={"ports": "80,443", "banner": True})
    argv_ps = portscan.build_argv(req_ps)
    assert argv_ps[0] == sys.executable
    assert "-t" in argv_ps and "127.0.0.1" in argv_ps
    assert "-p" in argv_ps and "80,443" in argv_ps
    assert "--banner" in argv_ps

    # 3. Test Arsenal SQLi
    sqli = registry.get("arsenal.sqli")
    req_sqli = ToolRequest(tool="arsenal.sqli", target="http://test.local/login", parameters={"params": "u=FUZZ", "method": "POST"})
    argv_sqli = sqli.build_argv(req_sqli)
    assert argv_sqli[0] == sys.executable
    assert "-u" in argv_sqli and "http://test.local/login" in argv_sqli
    assert "-p" in argv_sqli and "u=FUZZ" in argv_sqli
    assert "--method" in argv_sqli and "POST" in argv_sqli

    # 4. Test Sqlmap
    sqlmap = registry.get("sqlmap")
    req_sm = ToolRequest(tool="sqlmap", target="http://test.local/vuln.php?id=1", parameters={"level": 2, "risk": 2})
    argv_sm = sqlmap.build_argv(req_sm)
    assert argv_sm[0] == "sqlmap"
    assert "--level" in argv_sm and "2" in argv_sm
    assert "--risk" in argv_sm and "2" in argv_sm


def test_tactical_combat_mode_and_knowledge_hub(tmp_path: Optional[Path] = None):
    import tempfile
    if tmp_path is None:
        _td = tempfile.TemporaryDirectory()
        tmp_path = Path(_td.name)
    graph = ProbabilisticAttackGraph(goal_node_id="target_admin")
    graph.add_state_node("recon_info", "Recon", achieved=True)
    graph.add_state_node("foothold_access", "Foothold", achieved=False)
    graph.add_state_node("target_admin", "Admin", achieved=False)
    graph.add_transition("recon_info", "foothold_access", success_prob=0.8)
    graph.add_transition("foothold_access", "target_admin", success_prob=0.7)

    ledger = ArenaLedger()
    ledger.register_strategist("claude-3-5-sonnet", "Claude", "claude-3-5-sonnet")
    ledger.register_strategist("deepseek-v3", "DeepSeek", "deepseek-chat")

    # Give DeepSeek initial score
    ledger.reward_points("deepseek-v3", 100.0)
    assert ledger.can_afford("deepseek-v3", 50)
    assert not ledger.can_afford("claude-3-5-sonnet", 50)

    arbiter = TheArbiter(graph=graph, ledger=ledger)
    hub = LiveSecurityKnowledgeHub(db_path=tmp_path / "test_kb.db")

    # Claude tries but cannot afford
    fail_res = arbiter.execute_tactical_combat(
        strategist_id="claude-3-5-sonnet",
        target_node="foothold_access",
        knowledge_hub=hub,
        cost_points=50,
    )
    assert not fail_res.success
    assert "积分不足" in fail_res.action_log[0]

    # DeepSeek enters tactical combat
    init_prob = graph.calculate_goal_probability()
    success_res = arbiter.execute_tactical_combat(
        strategist_id="deepseek-v3",
        target_node="foothold_access",
        knowledge_hub=hub,
        cost_points=50,
        bounty_reward=120,
    )
    assert success_res.success
    assert success_res.delta_p > 0.0
    assert "foothold_access" in graph.achieved_nodes
    assert success_res.lead_captured  # DeepSeek captures lead
    assert ledger.current_leader_id == "deepseek-v3"
    assert success_res.reward_points == 120
    assert len(success_res.knowledge_references) > 0

    # Probability to goal must have risen
    post_prob = graph.calculate_goal_probability()
    assert post_prob > init_prob


def test_mission_arena_bridge():
    graph = ProbabilisticAttackGraph(goal_node_id="target_admin")
    graph.add_state_node("recon_info", "Recon", achieved=False)
    graph.add_state_node("waf_identified", "WAF", achieved=False)
    graph.add_state_node("foothold_access", "Foothold", achieved=False)
    graph.add_transition("recon_info", "waf_identified", success_prob=0.9)
    graph.add_transition("waf_identified", "foothold_access", success_prob=0.8)

    ledger = ArenaLedger()
    ledger.register_strategist("claude-3-5-sonnet", "Claude", "claude-3-5-sonnet")
    arbiter = TheArbiter(graph=graph, ledger=ledger)
    bridge = MissionArenaBridge(arbiter)

    from tonmen.missions import MissionPlan
    plan = MissionPlan.create(target="800211.com", steps=[])
    run = MissionRun.create(plan)
    from datetime import datetime
    now = datetime.now()
    run.evidence.append(
        EvidenceRecord(
            id="ev-1",
            tool="arsenal.portscan",
            target="800211.com",
            argv=("python", "port_scanner.py", "-t", "800211.com", "-p", "80,443"),
            exit_code=0,
            stdout="Discovered open ports: 80, 443",
            stderr="",
            started_at=now,
            finished_at=now,
        )
    )
    run.evidence.append(
        EvidenceRecord(
            id="ev-2",
            tool="arsenal.waf",
            target="800211.com",
            argv=("python", "script.py", "-t", "800211.com"),
            exit_code=0,
            stdout="Cloudflare WAF detected on 800211.com",
            stderr="",
            started_at=now,
            finished_at=now,
        )
    )

    eval_result = bridge.sync_mission_evidence(run)
    assert eval_result["round"] == 1
    assert "recon_info" in graph.achieved_nodes
    assert "waf_identified" in graph.achieved_nodes
