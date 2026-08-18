# TONMEN Runtime Boundaries

This document records runtime invariants that are enforced independently of Planner or Local AI behavior.

## Scope is not constructor-dependent

`TonmenRuntime.forge()` and `TonmenRuntime.sentinel()` both construct `TargetScope` from configured allow/deny rules and attach it to `PolicyEngine`.

`genesis()` remains a component-assembly layer without an Executor. Selecting Forge must not turn an out-of-scope target into an executable request.

## Typed execution only

Tool execution remains:

```text
ToolRequest
  -> registered ToolAdapter.validate()
  -> Scope / Policy
  -> non-consuming Approval validation when required
  -> declared local readiness / binary-identity preflight
  -> consume one-shot Approval immediately before execution
  -> ToolAdapter.build_argv()
  -> shell=False Executor
```

Arbitrary shell execution remains disabled.

## External binary identity is part of readiness

A filename match is not sufficient readiness for an external CLI whose name may collide with another package.

`httpx` is the first explicit identity-enforced adapter because the Python `httpx` package can install a CLI with the same executable name as ProjectDiscovery HTTPx. TONMEN now scans PATH candidates in order and probes the CLI contract it actually depends on (`-silent`, `-status-code`, `-tech-detect`, `-timeout`).

If an incompatible `httpx` shadows a later compatible ProjectDiscovery binary, Doctor/readiness records the rejected candidate and selects the later compatible executable. Real local execution uses the **verified absolute path** rather than resolving the name through PATH a second time.

If no compatible candidate exists, readiness fails with `wrong_binary_identity` instead of showing a false green state.

Injected/fake runners remain independent of host-installed external tools for deterministic tests.

## Approval validation versus consumption

Approval grants remain single-use and tool+target bound.

TONMEN first validates the grant without consuming it. Declared readiness/identity checks then run. Only after preflight succeeds is the grant consumed immediately before execution.

This prevents an environment/preflight failure from silently burning a valid grant while preserving the invariant that an actual higher-risk execution attempt consumes a fresh approval.

## Bounded process output

Each stdout/stderr stream is capped independently before it is persisted as Evidence or emitted through the live output event stream.

Default cap: **2 MiB per stream**.

When a stream exceeds the cap:

- the process pipe continues to be drained so the child cannot deadlock on a full pipe;
- additional bytes are discarded;
- persisted Evidence contains an explicit truncation marker;
- ToolResult metadata records stdout/stderr truncation and the configured byte cap.

The same bound applies to injected/test runners and timeout evidence.

## Typed process timeout + Mission wall-clock budget

Discovery-oriented tools continue to use the generic Executor timeout unless their adapter declares a bounded `ToolSpec.execution_timeout_seconds`.

Approval-gated Nuclei validation currently declares a **600 second** typed process budget because a bounded medium/high/critical template set can legitimately exceed the generic 120 second discovery-oriented default.

MissionLoop separately maintains a global wall-clock ceiling. Coordinator derives the remaining global budget from `MissionRun.started_at` plus the latest `loop.session.max_duration_seconds` and passes that value to Executor.

The effective process timeout is therefore:

```text
min(
  adapter typed execution timeout OR generic executor timeout,
  remaining mission wall-clock budget
)
```

The default MissionLoop duration is **900 seconds** and remains configurable/bounded to at most 3600 seconds.

Approval waits do not silently reset the mission-wide wall-clock boundary.

### Approval-gated validation timeout recovery

A timeout from an approval-gated validation step is **not** converted into success and is **not** allowed to terminate the entire Mission immediately.

TONMEN instead:

1. persists timeout Evidence (`exit_code=124`);
2. returns the Step to `WAITING_APPROVAL`;
3. records `retry_requires_fresh_approval=true`;
4. keeps the Mission at `WAITING_APPROVAL`;
5. requires a newly issued approval grant before another attempt.

The consumed grant is never reused and TONMEN never auto-retries a higher-risk validation action.

Discovery timeout behavior remains separate: bounded discovery timeouts may degrade a Step while preserving partial Evidence.

## Nuclei template binding

Nuclei readiness verifies the configured/default template root. The exact same resolved root is passed to Nuclei with `-t` during execution.

This prevents a state where readiness validates one template tree while the executable implicitly selects another.

Nuclei remains approval-gated by Policy.

## Credential-like URL query rejection

HTTP(S) targets reject URL user/password credentials and credential-like query parameter names before they can enter a Mission Plan.

Examples include token/access-token/API-key/password/session/JWT/auth/code-style keys.

This is intentionally rejection rather than logging redaction: TONMEN's current autonomous assessment path does not need target-URL secrets, so the safer invariant is to prevent such values from entering Plan, argv, Evidence, events, Chronicle or Reports at all.

Ordinary non-sensitive query parameters remain valid within existing URL validation rules.

## Authenticated Audit trail

New `audit.jsonl` records form an **HMAC-SHA256 chain**. The HMAC key is generated locally, stored separately from the JSONL and restricted to mode `0600` where the platform permits it.

Before append, TONMEN verifies the existing authenticated chain. A corrupted or unverifiable chain is not extended.

Legacy JSONL records remain compatible: the entire legacy prefix is deterministically folded into the `prev_hash` anchor of the first authenticated event. Once that event exists, later mutation of the legacy prefix breaks verification.

This protects against silent modification of the audit file without the separate integrity key. It is not a hardware-rooted signature and should not be described as protection against an attacker who can also obtain/replace both the audit file and its private key.

## Authenticated Chronicle snapshots

New mission snapshots under `missions/` are authenticated with **HMAC-SHA256** using a separate local `0600` Chronicle key. The HMAC covers the complete serialized Plan, Run, Evidence records, observations and Evidence Graph.

- `load()` rejects an authenticated snapshot whose HMAC is invalid or whose key is missing;
- `list()` omits invalid authenticated snapshots rather than presenting them as normal mission history;
- schema-1 snapshots without an integrity block remain readable for migration and are upgraded on their next save;
- snapshot writes remain atomic and private.

As with Audit, the integrity key is local software state, not an external/HSM trust anchor.

## Local Console control boundary

The Console binds only to loopback. Mutating requests require a per-server random CSRF token and same-Origin/Host validation. Responses also use restrictive CSP, `X-Frame-Options: DENY`, `nosniff`, and `Referrer-Policy: no-referrer`.

TONMEN does not currently implement a multi-user remote login service; the Console is intentionally a local operator surface rather than a network management plane.

## REPORT_ONLY remains mandatory

`MissionLoopPolicy(report_only=True)` cannot be disabled. Payload execution, credential capture, session takeover, persistence and destructive end-stage actions remain outside the autonomous execution path.
