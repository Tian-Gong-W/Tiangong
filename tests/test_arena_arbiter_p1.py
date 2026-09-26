from tonmen.arena import (
    NodeType,
    LootCategory,
    LootItem,
    TacticalProposal,
    ProbabilisticAttackGraph,
    TheArbiter,
)


def test_probabilistic_graph_marginal_progress():
    pag = ProbabilisticAttackGraph(goal_node_id="target_admin")

    # Construct Attack Graph topology:
    # entry_waf -> web_app -> low_priv -> target_admin (OR)
    # AND node: exploit requires [cve_vuln AND waf_bypassed]
    pag.add_state_node("recon_info", "Recon Done", NodeType.STATE_NODE, achieved=True)
    pag.add_state_node("waf_bypassed", "WAF Bypassed", NodeType.OR_NODE, achieved=False)
    pag.add_state_node("cve_vuln", "CVE Identified", NodeType.OR_NODE, achieved=False)
    pag.add_state_node("exploit_success", "Exploit Success", NodeType.AND_NODE, achieved=False)
    pag.add_state_node("target_admin", "Admin Access", NodeType.OR_NODE, achieved=False)

    pag.add_transition("recon_info", "waf_bypassed", success_prob=0.8)
    pag.add_transition("recon_info", "cve_vuln", success_prob=0.9)
    pag.add_transition("waf_bypassed", "exploit_success", success_prob=0.95)
    pag.add_transition("cve_vuln", "exploit_success", success_prob=0.95)
    pag.add_transition("exploit_success", "target_admin", success_prob=0.99)

    # Initial probability of reaching target_admin
    p_initial = pag.calculate_goal_probability()
    assert 0.0 <= p_initial < 1.0

    # Loot 1: WAF Bypassed
    loot_waf = LootItem(id="l1", title="WAF Bypass Found", category=LootCategory.BYPASS)
    delta_p1 = pag.commit_loot(loot_waf, ["waf_bypassed"])
    assert delta_p1 >= 0.0

    p_after_waf = pag.calculate_goal_probability()
    assert p_after_waf >= p_initial

    # Loot 2: CVE Identified -> Triggers AND node
    loot_cve = LootItem(id="l2", title="CVE Confirmed", category=LootCategory.ACCESS)
    delta_p2 = pag.commit_loot(loot_cve, ["cve_vuln"])
    p_after_cve = pag.calculate_goal_probability()
    assert p_after_cve >= p_after_waf

    # Loot 3: Direct Admin
    loot_admin = LootItem(id="l3", title="Admin Shell", category=LootCategory.ADMIN)
    delta_p3 = pag.commit_loot(loot_admin, ["target_admin"])
    assert pag.calculate_goal_probability() == 1.0


def test_arbiter_3d_scoring_and_command_shift():
    arbiter = TheArbiter(circuit_low_score_threshold=15.0)
    arbiter.register_strategist("claude", "Claude 3.5 Sonnet", "claude-3-5-sonnet")
    arbiter.register_strategist("deepseek", "DeepSeek-V3", "deepseek-v3")
    arbiter.register_strategist("gpt4o", "GPT-4o", "gpt-4o")

    # Initial leader is claude
    assert arbiter.ledger.current_leader_id == "claude"

    # Round 1: DeepSeek performs exceptionally well
    prop_claude = TacticalProposal(
        proposal_id="p-c1",
        strategist_id="claude",
        hypothesis="Brute force login",
        target_id="target-1",
        risk_level=4.0,
    )
    prop_deepseek = TacticalProposal(
        proposal_id="p-d1",
        strategist_id="deepseek",
        hypothesis="Logical IDOR bypass",
        target_id="target-1",
        risk_level=1.0,
    )
    prop_gpt = TacticalProposal(
        proposal_id="p-g1",
        strategist_id="gpt4o",
        hypothesis="Generic port scan",
        target_id="target-1",
        risk_level=2.0,
    )

    results = {
        "p-c1": {"successful_actions_count": 1, "error": "rate_limited"},
        "p-d1": {"successful_actions_count": 5, "unlocked_nodes": ["recon_info"], "loot_category": LootCategory.BYPASS},
        "p-g1": {"successful_actions_count": 2},
    }

    round1 = arbiter.evaluate_round([prop_claude, prop_deepseek, prop_gpt], results)
    assert round1["round"] == 1

    # Round 2: DeepSeek leads again by >30% margin -> triggers Command Shift
    results2 = {
        "p-c1": {"successful_actions_count": 1},
        "p-d1": {"successful_actions_count": 8, "unlocked_nodes": ["goal_objective"], "loot_category": LootCategory.ADMIN},
        "p-g1": {"successful_actions_count": 1, "error": "timeout"},
    }
    round2 = arbiter.evaluate_round([prop_claude, prop_deepseek, prop_gpt], results2)
    assert round2["round"] == 2

    # Verify Command Shift to DeepSeek
    assert arbiter.ledger.current_leader_id == "deepseek"

    # Verify Subagent Looting: The bottom agent loses 1 subagent to the winner
    status = arbiter.get_status()
    leader_subagents = next(s["subagents_count"] for s in status["ledger"]["strategists"] if s["id"] == "deepseek")
    assert leader_subagents > 3  # Looted from loser
