# TONMEN Capability Matrix

TONMEN separates **analysis** from **execution authority**. New capabilities may inspect evidence and propose actions, but Scope, Policy, Approval and typed Tool Adapters remain the execution boundary.

## Operator workflow

The Console is organized around six operator tasks:

1. **Start mission** — choose an explicitly authorized target and bounded execution budget.
2. **Generate test plan** — preview tools, parameters, risk and approval boundaries before execution.
3. **Live execution** — inspect the actual tool, argv, stdout, stderr, exit code and lifecycle events.
4. **Data / Evidence** — inspect evidence-backed Host, Service, Web and Finding facts.
5. **Approval** — handle only steps that require explicit human authorization.
6. **Records / Delete** — inspect reports/history and remove terminal mission records.

Internal architecture modules remain available under the Console's Advanced section, but they are not primary operator navigation.

## Current executable capabilities

| Domain | Capability | State | Execution boundary |
|---|---|---|---|
| Network discovery | Nmap TCP reachability / bounded port scan | Active | Scope + typed adapter + shell=False |
| Web discovery | HTTPx status/title/technology metadata | Active | Scope + typed adapter + shell=False |
| Web crawling | Built-in HTML link crawler | Active | Strict same-origin, bounded pages/depth/response size, no form submission |
| Web validation | Nuclei template validation | Approval gated | Scope + readiness + single-use Tool/Target Grant |
| Evidence | argv/stdout/stderr/exit code provenance | Active | Chronicle + Evidence Graph |
| Intelligence | deterministic parsing of scanner/crawler evidence | Active | Evidence-linked facts only |
| Reasoning | deterministic next-action policy | Active | Cannot expand Scope or self-approve |

## Reverse / binary analysis — next stage

Reverse engineering should enter TONMEN as an **artifact intelligence** pipeline rather than an arbitrary shell feature.

Planned sequence:

1. Artifact intake with size limits and SHA-256 identity.
2. File type / architecture identification.
3. ELF / PE / Mach-O metadata and mitigation inspection.
4. Strings, symbols, imports/exports, sections and relocation metadata.
5. Optional disassembly backend behind a typed adapter (for example Capstone or a headless reverse-analysis engine).
6. Evidence-linked control-flow / call-site observations.
7. Human-reviewed candidate exploitability assessment.

Binary analysis output may recommend further validation, but must not automatically generate or execute unrestricted shellcode, ROP payloads or persistence actions.

## Session / interception / hijack-risk analysis — next stage

TONMEN may safely automate **risk detection** for interception and session-hijack conditions:

- Cookie Secure / HttpOnly / SameSite policy.
- CORS policy and credential exposure.
- Redirect-chain and cross-origin transition analysis.
- TLS certificate / protocol posture.
- Cache and security header posture.
- DNS / proxy / transport anomalies from authorized evidence.
- Lab-only controlled validation where explicit approval is required.

Automated credential theft, unauthorized session takeover, malicious MITM and persistence are outside the autonomous execution path.

## Penetration workflow expansion

The intended governed chain is:

```text
Authorized Target
    ↓
Scope
    ↓
Network + Web Discovery
    ↓
Bounded Crawler
    ↓
Evidence / Intelligence
    ↓
Planner + Reasoner recommendation
    ↓
Approval Gate for higher-risk validation
    ↓
Typed Validation Adapter
    ↓
Evidence-backed Report
```

Future discovery adapters should be added one capability at a time with explicit parameter bounds, readiness checks, test fixtures and evidence parsers. The Mission Loop must never synthesize free-form shell commands or add tools at runtime.
