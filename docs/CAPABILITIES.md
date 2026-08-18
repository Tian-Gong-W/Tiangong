# TONMEN Capability Matrix

TONMEN separates **analysis** from **execution authority**. New capabilities may inspect evidence and propose actions, but Scope, Policy, Approval and typed Tool Adapters remain the execution boundary.

## Operator workflow

The Console is organized around six operator tasks:

1. **Start mission** — choose an explicitly authorized target and bounded execution budget.
2. **Generate test plan** — preview candidate capabilities, seed parameters, risk and approval boundaries before execution.
3. **Live execution** — inspect the actual tool, resolved parameters, argv, stdout, stderr, exit code and lifecycle events.
4. **Data / Evidence** — inspect evidence-backed Host, Service, Web and Finding facts.
5. **Approval** — handle only steps that require explicit human authorization.
6. **Records / Delete** — inspect reports/history and remove terminal mission records.

Internal architecture modules remain available under the Console's Advanced section, but they are not primary operator navigation.

## Adaptive mission contract

A mission is no longer treated as a blind fixed scanner sequence. The initial plan is a set of governed candidate capabilities. Before each candidate runs, TONMEN rebuilds a live **Target Profile** from recorded evidence and decides whether that branch is still justified.

The profile tracks:

- observed ports and services;
- web locations and technologies;
- evidence-backed findings and severity;
- unresolved questions (`unknowns`);
- evidence-linked hypotheses;
- a bounded complexity score used only to control analysis cost.

Evidence can therefore change both **whether a candidate capability runs** and its bounded parameters. For example, an absent web surface can suppress crawling/validation, while a richer confirmed web surface can raise crawler coverage within fixed page/depth limits.

### Cost and autonomy envelope

The adaptive layer may change strategy, but it cannot change governance ceilings:

- assessment council: **7-10 rounds**;
- subagents per round: **3-5**, selected dynamically from the live Target Profile;
- model/tool loops remain bounded by configured iteration, execution and wall-clock limits;
- Scope, Policy, Approval and typed adapter validation are immutable execution boundaries;
- no agent may create raw shell execution authority.

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
| Web validation | Nuclei template validation | Approval gated | Scope + readiness + single-use Tool/Target Grant |
| Evidence | argv/stdout/stderr/exit code provenance | Active | Chronicle + Evidence Graph |
| Intelligence | deterministic parsing of scanner/crawler evidence | Active | Evidence-linked facts only |
| Target profile | ports/services/web/findings/unknowns/hypotheses | Active | Rebuilt only from recorded mission evidence |
| Adaptive parameters | tool budgets derived from current profile | Active | Adapter limits remain authoritative |
| Adaptive branch gate | skip unjustified candidate capabilities | Active | Cannot add Scope or bypass Policy |
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

## Session / interception risk analysis — next stage

TONMEN may safely automate **risk detection** for interception and session-security conditions:

- Cookie Secure / HttpOnly / SameSite policy.
- CORS policy and credential exposure risk.
- Redirect-chain and cross-origin transition analysis.
- TLS certificate / protocol posture.
- Cache and security header posture.
- DNS / proxy / transport anomalies from authorized evidence.
- Lab-only controlled validation where explicit approval is required.

Credential capture, unauthorized session takeover, malicious MITM and persistence are outside the autonomous execution path.

## Evolving workflow

```text
Authorized Target
    ↓
Scope / Policy
    ↓
Candidate Capabilities
    ↓
Execute one bounded observation
    ↓
Evidence Graph
    ↓
Target Profile
    ↓
Unknowns + Hypotheses
    ↓
Adaptive Reasoner
    ├─ Skip unjustified branch
    ├─ Continue with changed bounded parameters
    ├─ Request approval for validation
    └─ Stop and synthesize report
    ↓
Dynamic 3-5 Agent Council
    ↓
7-10 bounded assessment rounds
    ↓
REPORT ONLY
```

Future adapters should be added one capability at a time with explicit parameter bounds, readiness checks, test fixtures and evidence parsers. The Mission Loop must never synthesize free-form shell commands or add unrestricted execution authority at runtime.
