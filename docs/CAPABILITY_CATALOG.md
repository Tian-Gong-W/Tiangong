# TONMEN Capability Catalog

TONMEN plans **semantic capabilities**, not a hard-coded scanner sequence.

The catalog is read-only planning infrastructure. It never executes a command and never grants Scope, Approval, or Policy authority.

## Adapter declaration

Every adaptively plannable `ToolAdapter` declares a `CapabilityPlanningSpec` on its `ToolSpec`:

- `target_kinds` — target classes the capability can reason about;
- `seed_for` — target classes for which the capability can act as a minimal seed;
- `target_mode` — whether the adapter receives the original target or host-only target;
- `requires_profile` — boolean properties that must hold on the live Target Profile;
- `requires_capabilities` — semantic outputs that must already have been produced by successful/degraded governed steps;
- `basis_fact_kinds` — Intelligence Fact kinds that justify a planning revision;
- `resolves_unknowns` — Target Profile unknowns the capability is expected to reduce;
- `default_parameters` — typed safe seed parameters;
- `rationale` and `information_gain` — human-readable planning semantics;
- `information_gain_score` and `cost_score` — bounded deterministic planning inputs.

The central Planner therefore does not need to know that a specific binary is named `httpx`, `crawler`, `nuclei`, or anything else. For example, a future adapter can satisfy a downstream prerequisite by providing `http.metadata` or `endpoint.discover` under a completely different tool name.

## Deterministic eligibility

`CapabilityCatalog` evaluates each registered declaration against the current mission state.

A candidate can be eligible only if all applicable conditions hold:

1. it is not already queued in the plan;
2. its target kind is compatible;
3. declared Target Profile prerequisites hold;
4. declared semantic prerequisite capabilities were produced by previous successful/degraded steps;
5. its typed adapter accepts the candidate request;
6. Policy does not deny it;
7. readiness is satisfied for the current executor mode.

A rejected candidate remains visible in ranking audit data with the reason it was rejected. Rejection is not silently converted into a lower-confidence execution proposal.

## Deterministic score

Eligible candidates are ranked using bounded deterministic factors:

```text
information gain
+ unresolved questions expected to close
+ new semantic capabilities
+ bounded target complexity signal
- risk penalty
- cost penalty
- approval penalty
- readiness penalty
```

The exact score is an ordering signal, not execution authority. Policy and Approval remain separate hard boundaries.

Every adaptive `planning.revision` records:

- selected capability;
- deterministic base score;
- score reasons;
- top candidate rankings, including rejected reasons;
- expected information gain;
- supporting Fact IDs;
- unresolved profile questions;
- selection engine;
- `execution_authority=false`.

## Seed and dry-run envelope

`MissionPlanner.seed()` chooses from adapters that declare `seed_for=<target kind>`.

`MissionPlanner.plan()` is a **dry-run capability envelope**. It may display registered capabilities whose live prerequisites are not yet satisfied. That list is not an execution sequence. Runtime selection is performed only by `CapabilityCatalog.rank()` against the live Evidence Graph.

## Adapter-owned parameter adaptation

Tool-specific cost/coverage tuning is not encoded in the central resolver.

`AdaptiveParameterResolver` passes a bounded Target Profile context to `ToolAdapter.adapt_parameters()`. Each adapter can then vary only its own typed parameters within its validator limits. The central resolver re-validates the returned parameters before execution.

This allows a new adapter to own its parameter strategy without adding another central `if tool == ...` branch.

## Optional Local AI tie-break

Local AI cannot create candidates. It receives only bounded summaries of candidates already marked eligible by the deterministic catalog:

- tool identifier;
- deterministic score and reasons;
- semantic outputs/prerequisites;
- unknowns the capability may resolve;
- risk;
- approval requirement.

It does **not** receive candidate argv or execution parameters.

The model may return a `capability_preferences` list containing only:

- an already-supplied tool identifier;
- preference in `[-1, 1]`;
- rationale;
- existing Fact IDs.

TONMEN filters unknown tool identifiers and unknown Fact IDs before the preference reaches planning.

### Hard tie-break bounds

Deterministic ranking remains authoritative:

- only candidates within **5.0 deterministic score points** of the deterministic winner can receive an AI adjustment;
- AI adjustment is capped at **±2.5 points**;
- ineligible / Policy-denied / unready candidates receive zero AI adjustment;
- AI cannot alter risk, parameters, approval state, Scope, Policy, or adapter validation;
- if AI is disabled or fails, ranking is identical to deterministic catalog ranking.

When used, the revision records base score, AI preference, bounded adjustment, final score, whether the deterministic winner changed, and `selection_engine=capability_catalog+bounded_ai_tiebreak`.

## Governance invariant

The planning path is:

```text
Evidence Graph
  -> Target Profile
  -> Registry ToolSpec declarations
  -> CapabilityCatalog eligibility
  -> deterministic score
  -> optional bounded local-AI tie-break
  -> planning.revision (execution_authority=false)
  -> typed adapter validation
  -> Scope / Policy / Approval
  -> Executor
```

No planner, model, catalog entry, or ranking score can independently execute a tool.
