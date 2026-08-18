# TONMEN Capability Matrix

TONMEN separates **analysis** from **execution authority**. New capabilities may inspect evidence and propose actions, but Scope, Policy, Approval and typed Tool Adapters remain the execution boundary.

## Operator workflow

The Console is organized around six operator tasks:

1. **Start mission** — choose an explicitly authorized target and bounded execution budget.
2. **Generate test plan** — preview the committed seed plus the governed capability pool, risk and approval boundaries before execution.
3. **Live execution** — inspect the actual tool, resolved parameters, argv, stdout, stderr, exit code, replanning rationale and lifecycle events.
4. **Data / Evidence** — inspect evidence-backed Host, Service, Web and Finding facts.
5. **Approval** — handle only steps that require explicit human authorization.
6. **Records / Delete** — inspect reports/history and remove terminal mission records.

Internal architecture modules remain available under the Console's Advanced section, but they are not primary operator navigation.

## Adaptive mission contract

An autonomous mission does **not** commit a fixed `nmap -> httpx -> crawler -> nuclei` sequence.

The Mission Loop begins with the smallest target-appropriate seed:

- an explicit HTTP(S) target starts with HTTP metadata discovery (`httpx`);
- a host/IP target starts with a minimal network observation (`nmap`).

After that seed executes, TONMEN rebuilds a live **Target Profile** from recorded evidence and may append one new governed capability. The next step becomes part of the mission only when the evidence justifies it. A non-Web host can therefore stop after network discovery, while a confirmed Web surface can grow into HTTP observation, bounded crawling and eventually an approval-gated validation proposal.

Every appended step creates a `planning.revision` graph node containing:

- the proposed capability and target;
- risk and approval requirement;
- the evidence/fact IDs supporting the revision;
- the planner rationale;
- expected information gain;
- currently unresolved profile questions;
- `execution_authority = false`.

A planning revision cannot itself run a command. The new step must still pass Scope, Policy, readiness, typed adapter validation and the normal Executor path.

### Candidate envelope vs committed plan

`MissionPlanner.plan()` remains a dry-run view of the bounded capability envelope an operator may inspect. `MissionPlanner.seed()` is the committed start of an adaptive mission. The Console plan preview exposes both clearly:

- **Seed** — committed first step, including its typed argv preview.
- **Candidate capability pool** — possible later capabilities; these are not yet committed and their future argv is not presented as final because evidence may change bounded parameters.

The actual plan stored in Chronicle grows immutably: each revision keeps the same plan identity and appends a unique step. Previous steps cannot be silently rewritten or reordered.

## Target Profile and bounded adaptation

The profile tracks:

- observed ports and services;
- Web locations and technologies;
- evidence-backed findings and severity;
- unresolved questions (`unknowns`);
- evidence-linked hypotheses;
- a bounded complexity score used only to control analysis cost.

Evidence can therefore change **whether another capability is added** and its bounded parameters. For example, an absent Web surface ends the Web branch, while a richer confirmed Web surface can raise crawler coverage within fixed page/depth limits.

### Cost and autonomy envelope

The adaptive layer may change strategy, but it cannot change governance ceilings:

- assessment council: **7-10 rounds**;
- subagents per round: **3-5**, selected dynamically from the live Target Profile;
- model/tool loops remain bounded by configured iteration, execution and wall-clock limits;
- Scope, Policy, Approval and typed adapter validation are immutable execution boundaries;
- no agent may create raw shell execution authority;
- duplicate plan-step identities are rejected and completed history is append-only within a plan revision.

A sparse target can converge near the lower bound. A complex target with high-confidence evidence can use more review rounds and up to five specialist subagents, but never exceed the fixed envelope.

## Mandatory report-only boundary

TONMEN is designed to stop at assessment and reporting. The `MissionLoopPolicy` report-only setting is mandatory and cannot be disabled. Policy also blocks tool capabilities that represent final active actions such as direct payload execution, credential capture, session takeover or persistence.

The final product may still describe evidence, prerequisites, risk, impact, remediation and a non-executed validation plan in the report. The runtime itself does not perform the final active step.

## Current executable capabilities

| Domain | Capability | State | Execution boundary |
|---|---|---|---|
| Network discovery | Nmap TCP reachability / bounded port scan | Active | Scope + typed adapter + shell=False |
| Web discovery | HTTPx status/title/technology metadata | Active | Scope + typed adapter + shell=False |
| Web crawling | Built-in HTML link crawler | Active | Strict same-origin, bounded pages/depth/response size, no form submission |
| Web/session posture | Cookie flag, HSTS/CSP and CORS response observation | Active passive | Same-origin crawler response only; cookie values are never recorded |
| Web validation | Nuclei template validation | Approval gated | Scope + readiness + single-use Tool/Target Grant |
| Evidence | argv/stdout/stderr/exit code provenance | Active | Chronicle + Evidence Graph |
| Intelligence | deterministic parsing of scanner/crawler evidence | Active | Evidence-linked facts only |
| Target profile | ports/services/web/findings/unknowns/hypotheses | Active | Rebuilt only from recorded mission evidence |
| Adaptive parameters | tool budgets derived from current profile | Active | Adapter limits remain authoritative |
| Adaptive plan growth | append one justified capability after new evidence | Active | `planning.revision`; no execution authority |
| Adaptive branch gate | suppress unjustified capabilities | Active | Cannot add Scope or bypass Policy |
| Assessment council | dynamic 3-5 evidence-review roles, 7-10 rounds | Active | Read-only; no execution authority |
| Reasoning | evidence-driven next-action policy | Active | Cannot expand Scope or self-approve |

## Reverse / binary analysis — next stage

Reverse engineering should enter TONMEN as an **artifact intelligence** pipeline rather than an arbitrary shell feature.

Planned sequence:

1. Artifact intake with size limits and SHA-256 identity.
2. File type / architecture identification.
3. ELF / PE / Mach-O metadata and mitigation inspection.
4. Strings, symbols, imports/exports, sections and relocation metadata.
5. Optional disassembly backend behind a typed adapter (for example Capstone or a headless reverse-analysis engine).
6. Evidence-linked control-flow / call-site observations.
7. Human-reviewed risk and impact assessment.

Binary analysis output may recommend further controlled validation, but must not automatically execute unrestricted payloads or persistence actions.

## Session / interception risk analysis — passive foundation active

The governed crawler now performs **observation-only** session/Web posture collection on responses it was already authorized to retrieve:

- Cookie names plus `Secure`, `HttpOnly`, `SameSite` and `Partitioned` flags.
- Whether HSTS, CSP, X-Content-Type-Options, Referrer-Policy, frame policy, Permissions-Policy, Cache-Control are present.
- Returned CORS allow-origin / allow-credentials posture.
- Whether the accepted response arrived through a same-origin redirect.

The crawler **never records Cookie values**. It does not inject credentials, submit forms, send active session-takeover payloads or leave its strict same-origin boundary.

Entry-page observations can create conservative evidence-linked findings for:

- missing HSTS on HTTPS;
- missing CSP (informational);
- Cookie policy gaps such as missing Secure/HttpOnly/SameSite flags;
- wildcard CORS responses.

This is posture evidence, not proof of account compromise. Active CORS exploitation, credential capture, session replay/takeover, malicious MITM and persistence remain outside the autonomous path.

Still planned for this domain:

- richer redirect-chain provenance;
- TLS certificate / protocol posture;
- DNS / proxy / transport anomaly evidence;
- lab-only controlled validation where explicit approval is required.

## Evolving workflow

```text
Authorized Target
    ↓
Scope / Policy
    ↓
Minimal target-aware Seed
    ↓
Execute one bounded observation
    ↓
Evidence Graph
    ↓
Target Profile
    ↓
Unknowns + Hypotheses
    ↓
Adaptive Planner + Reasoner
    ├─ no evidence for another branch -> stop
    ├─ append one governed capability -> planning.revision
    ├─ change bounded parameters -> typed adapter validation
    └─ request approval for validation
    ↓
Execute next justified capability
    ↺ rebuild profile and replan
    ↓
Dynamic 3-5 Agent Council
    ↓
7-10 bounded assessment rounds
    ↓
REPORT ONLY
```

Future adapters should be added one capability at a time with explicit parameter bounds, readiness checks, test fixtures and evidence parsers. The Mission Loop must never synthesize free-form shell commands, expand Scope or add unrestricted execution authority at runtime.
