from __future__ import annotations

from typing import Any

from tonmen.agents import MissionPlanner
from tonmen.ai import LeadAIOrchestrator, ProviderHub
from tonmen.core.runtime import TonmenRuntime
from tonmen.loop import MissionLoopPolicy
from tonmen.workers import RemoteWorkerExecutor


def _issue(code: str, message: str, *, remediation: str | None = None, **metadata: object) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "remediation": remediation,
        "metadata": metadata,
    }


def build_mission_preflight(
    runtime: TonmenRuntime,
    target: str,
    policy: MissionLoopPolicy | None = None,
) -> dict[str, Any]:
    """Build a governed mission preview without executing a scanner.

    Planning may perform passive DNS resolution through the existing Resolved Asset
    Set. No tool execution, Approval Grant, Scope mutation, Provider model call, or
    Worker dispatch is performed here.
    """

    resolved_policy = policy or MissionLoopPolicy()
    plan = MissionPlanner(runtime).plan(target)
    executor = runtime.executor
    worker_mode = isinstance(executor, RemoteWorkerExecutor)

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    longest_step_timeout = 0

    for step in plan.steps:
        timeout_seconds = runtime.config.timeout_for(step.tool)
        longest_step_timeout = max(longest_step_timeout, timeout_seconds)
        readiness = runtime.registry.get(step.tool).readiness()
        if worker_mode:
            readiness_payload = {
                "ready": None,
                "code": "deferred_to_worker",
                "detail": "Worker health/readiness is checked immediately before remote dispatch.",
                "remediation": None,
                "scope": "worker",
            }
        else:
            readiness_payload = {
                "ready": readiness.ready,
                "code": readiness.code,
                "detail": readiness.detail,
                "remediation": readiness.remediation,
                "scope": "local",
            }
            if not readiness.ready:
                problem = _issue(
                    "tool_not_ready",
                    f"{step.tool} is not ready: {readiness.detail}",
                    remediation=readiness.remediation,
                    tool=step.tool,
                    target=step.target,
                    requires_approval=step.requires_approval,
                )
                # Missing a future approval-gated tool should not stop low-risk
                # discovery from starting, but the operator must see the boundary.
                (warnings if step.requires_approval else blockers).append(problem)

        steps.append(
            {
                "id": step.id,
                "tool": step.tool,
                "target": step.target,
                "risk": step.risk,
                "requires_approval": step.requires_approval,
                "timeout_seconds": timeout_seconds,
                "readiness": readiness_payload,
            }
        )

    if longest_step_timeout and resolved_policy.max_duration_seconds < longest_step_timeout:
        warnings.append(
            _issue(
                "mission_budget_shorter_than_step_timeout",
                (
                    f"Mission duration {resolved_policy.max_duration_seconds}s is shorter than the longest "
                    f"planned tool timeout {longest_step_timeout}s."
                ),
                remediation=(
                    "Increase the Mission duration or lower the relevant [timeouts] value so the operator-visible "
                    "Mission budget and per-tool ceiling are coherent."
                ),
                mission_duration_seconds=resolved_policy.max_duration_seconds,
                longest_step_timeout_seconds=longest_step_timeout,
            )
        )

    metadata = dict(plan.metadata or {})
    asset_set = dict(metadata.get("resolved_assets") or {})
    coverage = dict(metadata.get("coverage_plan") or {})
    resolved_addresses = list(asset_set.get("addresses") or [])
    needs_scope = list(asset_set.get("needs_scope") or coverage.get("needs_scope") or [])
    authorized_addresses = list(asset_set.get("authorized_addresses") or [])

    if needs_scope:
        warnings.append(
            _issue(
                "resolved_assets_need_scope",
                f"{len(needs_scope)} resolved address(es) are observations only and are not independently authorized.",
                remediation="Add only explicitly authorized IP/CIDR assets to Scope, then create a new Mission plan.",
                addresses=needs_scope,
            )
        )

    if len(resolved_addresses) > 1 and not coverage.get("resolved_ip_coverage_enabled"):
        warnings.append(
            _issue(
                "resolved_ip_coverage_disabled",
                "The hostname resolves to multiple addresses; direct resolved-IP Nmap coverage is not enabled.",
                remediation=(
                    "If those concrete addresses are explicitly authorized, add them to Scope and set "
                    "TONMEN_RESOLVED_IP_COVERAGE=1 before creating a new Mission."
                ),
                resolved_addresses=resolved_addresses,
            )
        )

    provider_hub = ProviderHub()
    provider_status = provider_hub.public_status()
    ready_provider_ids = [provider_id for provider_id in provider_hub.pool if provider_hub.is_ready(provider_id)]
    if not provider_hub.pool:
        warnings.append(
            _issue(
                "ai_provider_pool_empty",
                "Council model-provider pool is empty; subagents will use deterministic evidence review.",
                remediation=(
                    "Set TONMEN_AI_POOL=auto or an explicit provider list if model-backed Council review is desired."
                ),
            )
        )
    elif not ready_provider_ids:
        warnings.append(
            _issue(
                "ai_provider_pool_not_ready",
                "AI providers are configured but none are locally ready for Council routing.",
                remediation="Check Provider Hub credentials/login state and run explicit provider probes.",
                configured_pool=list(provider_hub.pool),
            )
        )

    lead_status = LeadAIOrchestrator().public_status()

    execution_plane: dict[str, Any]
    if worker_mode:
        pool = runtime.workers
        workers = list(pool.workers) if pool is not None else []
        execution_plane = {
            "mode": "worker",
            "worker_count": len(workers),
            "workers_with_secret": sum(1 for item in workers if item.secret_configured),
            "health_probe_deferred": True,
            "local_scanner_binaries_required": False,
        }
        if not workers:
            blockers.append(
                _issue(
                    "worker_pool_empty",
                    "Worker execution mode has no configured workers.",
                    remediation="Configure TONMEN_WORKERS with at least one governed Worker.",
                )
            )
    else:
        execution_plane = {
            "mode": "local",
            "worker_count": 0,
            "health_probe_deferred": False,
            "local_scanner_binaries_required": True,
        }

    return {
        "ready_to_start": not blockers,
        "target": target,
        "plan_id": plan.id,
        "plan": {
            "steps": len(plan.steps),
            "approval_gated_steps": sum(1 for step in plan.steps if step.requires_approval),
            "metadata": metadata,
        },
        "policy": {
            "max_iterations": resolved_policy.max_iterations,
            "max_executions": resolved_policy.max_executions,
            "max_repeat_decisions": resolved_policy.max_repeat_decisions,
            "max_duration_seconds": resolved_policy.max_duration_seconds,
            "assessment_rounds": resolved_policy.assessment_rounds,
            "subagents_per_round": resolved_policy.subagents_per_round,
            "longest_step_timeout_seconds": longest_step_timeout,
        },
        "execution_plane": execution_plane,
        "steps": steps,
        "assets": {
            "resolved_addresses": resolved_addresses,
            "authorized_addresses": authorized_addresses,
            "needs_scope": needs_scope,
            "coverage_enabled": bool(coverage.get("resolved_ip_coverage_enabled")),
            "direct_nmap_targets": list(coverage.get("direct_nmap_targets") or []),
            "deferred_due_to_execution_bound": list(coverage.get("deferred_due_to_execution_bound") or []),
        },
        "ai": {
            "lead": {
                "active": bool(lead_status.get("active")),
                "provider": lead_status.get("provider"),
                "model": lead_status.get("model"),
                "key_configured": bool(lead_status.get("key_configured")),
            },
            "council": {
                "pool": list(provider_hub.pool),
                "ready_providers": ready_provider_ids,
                "strategy": provider_status.get("strategy"),
                "mission_token_budget": provider_status.get("mission_token_budget"),
                "model_backed": bool(ready_provider_ids),
            },
            "secret_values_exposed": False,
            "raw_evidence_sent": False,
            "approval_tokens_sent": False,
        },
        "blockers": blockers,
        "warnings": warnings,
        "side_effects": {
            "scanner_executed": False,
            "worker_dispatched": False,
            "approval_issued": False,
            "scope_mutated": False,
            "provider_model_called": False,
            "dns_resolution_may_occur": True,
        },
    }
