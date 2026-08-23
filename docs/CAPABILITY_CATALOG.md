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
- `information_gain_score` and `cost_score` — bounded deterministic planning inputs;
- `include_in_baseline_envelope` — whether the capability appears in the historical operator/dry-run baseline envelope. `False` keeps a capability adaptive-only without removing it from live Catalog ranking.

The central Planner therefore does not need to know that a specific binary is named `httpx`, `crawler`, `api-intel`, `nuclei`, or anything else. A future adapter can satisfy a downstream prerequisite by providing semantic capabilities such as `http.metadata` or `endpoint.discover` under a completely different tool name.

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

### Frontier and lineage guards

Adaptive extension happens only at a completed execution frontier. Pending, running, or approval-gated steps prevent the Catalog from appending a capability behind them.

TONMEN also distinguishes a minimal autonomous seed lineage from a pre-built operator baseline envelope:

- a one-step seed may begin adaptive extension after that step settles;
- once extension begins, `planning.revision` provenance marks the mission as adaptive lineage;
- a multi-step plan with no `planning.revision` is treated as a pre-built baseline/dry-run envelope and is not silently expanded after completion.

This keeps approval position and persisted plan/run alignment stable while preserving evidence-driven growth for real seed-based missions.

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

Every adaptive `planning.revision` records selected capability, deterministic base score, score reasons, top candidate rankings (including rejected reasons), expected information gain, supporting Fact IDs, unresolved profile questions, selection engine, and `execution_authority=false`.

## Seed, baseline envelope, and adaptive-only capabilities

`MissionPlanner.seed()` chooses from adapters that declare `seed_for=<target kind>`.

`MissionPlanner.plan()` is a **dry-run baseline capability envelope**, not an execution sequence. Callers may explicitly request the full adaptive pool, but ordinary legacy/baseline execution does not silently gain extra network actions merely because the Registry grows.

Current adaptive-only built-ins include:

- `dns-intel` → `dns.resolve`, `address.discover`;
- `tls-intel` → `tls.handshake`, `certificate.inspect`;
- `api-intel` → `api.surface.observe`, `javascript.endpoint.extract`, `openapi.hint.observe`.

They remain available to live `CapabilityCatalog.rank()` whenever Target Profile evidence justifies them.

## DNS and TLS intelligence semantics

The built-in DNS and TLS adapters use Python standard-library runners and require no external `dig` or `openssl` dependency.

DNS intelligence is bounded to hostname identity evidence: A/AAAA addresses plus canonical/reverse names obtainable from the local resolver. It does not brute-force names or enumerate zones.

TLS intelligence performs one bounded handshake against an evidence-selected/default port and records protocol version, cipher, certificate SHA-256 fingerprint, subject, issuer, SANs, serial and validity metadata. It does not attempt credential use, session takeover, exploitation or protocol downgrade attacks.

Negative observations are evidence rather than mission crashes: an unresolved hostname or unavailable TLS handshake produces a structured DNS/TLS Fact so later planning can reason about the absence of that surface.

## API and static JavaScript intelligence semantics

`api-intel` is a bounded same-origin **static analysis** capability. It requires an already-confirmed HTTP metadata capability and is adaptive-only by default.

It may:

- fetch one confirmed same-origin entry page;
- inspect inline JavaScript text without executing it;
- fetch a bounded number of same-origin script assets;
- extract same-origin strings that resemble API, REST, RPC, GraphQL or versioned endpoint paths;
- record OpenAPI / Swagger / GraphQL technology hints;
- emit a structured summary even when no endpoint is observed, allowing `client_api_surface` uncertainty to close without inventing a positive result.

It does **not** execute JavaScript, submit forms, follow cross-origin scripts/redirects, capture credentials, replay sessions or perform API calls against extracted endpoints. Endpoint strings are evidence for later planning, not execution instructions.

`intelligence.api` facts feed Target Profile fields (`api_endpoints`, `api_hints`, `api_inspected`), Evidence Confidence, hypotheses and the bounded Local AI context. A negative static inspection remains unresolved/non-contradictory evidence rather than being treated as proof that no API exists.

## Adapter-owned parameter adaptation

Tool-specific cost/coverage tuning is not encoded in the central resolver.

`AdaptiveParameterResolver` passes a bounded Target Profile context to `ToolAdapter.adapt_parameters()`. Each adapter can then vary only its own typed parameters within its validator limits. The central resolver re-validates returned parameters before execution.

This allows a new adapter to own its parameter strategy without adding another central `if tool == ...` branch.

## Optional Local AI tie-break

Local AI cannot create candidates. It receives only bounded summaries of candidates already marked eligible by the deterministic catalog: tool identifier, deterministic score/reasons, semantic outputs/prerequisites, unknowns the capability may resolve, risk and approval requirement.

It does **not** receive candidate argv or execution parameters.

The model may return a `capability_preferences` list containing only an already-supplied tool identifier, preference in `[-1, 1]`, rationale and existing Fact IDs. TONMEN filters unknown tool identifiers and unknown Fact IDs before the preference reaches planning.

### Hard tie-break bounds

Deterministic ranking remains authoritative:

- only candidates within **5.0 deterministic score points** of the deterministic winner can receive an AI adjustment;
- AI adjustment is capped at **±2.5 points**;
- ineligible / Policy-denied / unready candidates receive zero AI adjustment;
- AI cannot alter risk, parameters, approval state, Scope, Policy, or adapter validation;
- if AI is disabled or fails, ranking is identical to deterministic catalog ranking.

When used, the revision records base score, AI preference, bounded adjustment, final score, whether the deterministic winner changed, and `selection_engine=capability_catalog+bounded_ai_tiebreak`.

## Governance invariant

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
