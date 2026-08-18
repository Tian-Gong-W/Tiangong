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
  -> Approval when required
  -> ToolAdapter.build_argv()
  -> shell=False Executor
```

Arbitrary shell execution remains disabled.

## Bounded process output

Each stdout/stderr stream is capped independently before it is persisted as Evidence or emitted through the live output event stream.

Default cap: **2 MiB per stream**.

When a stream exceeds the cap:

- the process pipe continues to be drained so the child cannot deadlock on a full pipe;
- additional bytes are discarded;
- persisted Evidence contains an explicit truncation marker;
- ToolResult metadata records stdout/stderr truncation and the configured byte cap.

The same bound applies to injected/test runners and timeout evidence.

## Mission wall-clock budget

MissionLoop still checks its monotonic iteration budget, and Coordinator additionally derives the remaining global wall-clock budget from `MissionRun.started_at` plus the latest `loop.session.max_duration_seconds`.

The remaining value is passed to Executor as a timeout ceiling. Executor always uses the minimum of:

- configured command timeout;
- remaining mission wall-clock budget;
- any narrower typed request-context timeout.

Approval waits therefore do not silently reset the mission-wide wall-clock boundary.

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
