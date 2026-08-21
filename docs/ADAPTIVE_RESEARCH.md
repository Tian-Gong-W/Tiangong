# Adaptive research planning

TONMEN's planner now has an incremental migration path from a fixed tool sequence
toward self-reliant, evidence-driven research.

## Principle

Give the runtime goals, evidence, constraints and capabilities — not a script.

The legacy `MissionPlanner.plan()` API remains available for the current
`MissionLoop`, but its ordering is derived from semantic capability metadata
rather than concrete tool names. New orchestration should use:

1. `MissionPlanner.bootstrap(target)` to create the minimum initial hypotheses
   and low-risk actions needed to establish a world model.
2. Reconcile resulting evidence into hypothesis state.
3. Call `MissionPlanner.decide_next(state)` to produce new `ActionProposal`
   candidates from the current state.
4. Pass every selected proposal through the existing Scope, Policy, Approval
   and Executor boundaries.
5. Stop when no allowed untried capability can reduce uncertainty, or when a
   budget/policy boundary says to stop.

## Safety invariants

Adaptive planning does not grant execution authority.

- Scope remains deny-by-default.
- DNS observations never expand Scope.
- Destructive actions remain disabled by default.
- Validation actions require explicit Approval.
- Tool adapters still validate structured parameters.
- Execution remains argv-based with `shell=False`.
- A planner proposal is only a proposal; Policy and Executor remain authoritative.

## Current migration boundary

This change introduces `CapabilitySpec`, `Hypothesis`, `ActionProposal`,
`bootstrap()` and `decide_next()` while preserving the current fixed-step
`MissionLoop` compatibility path. A later change can replace the loop's frozen
step traversal with an append-only action ledger/director without weakening the
existing governance boundary.
