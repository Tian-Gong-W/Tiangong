# TONMEN Local AI Advisory

TONMEN does not require an AI model or API key to start, scan, reason, approve, report, or use the Console. The deterministic Planner / Reasoner / Council path remains the default runtime.

## Default mode

```toml
[ai]
enabled = false
provider = "none"
model = ""
base_url = "http://127.0.0.1:11434"
timeout_seconds = 20
```

No API-key field exists in `TonmenConfig` and no cloud credential is stored by TONMEN.

## Optional local Ollama mode

A local Ollama model can be enabled explicitly:

```toml
[ai]
enabled = true
provider = "ollama"
model = "qwen3:8b"
base_url = "http://127.0.0.1:11434"
timeout_seconds = 20
```

TONMEN does not install or pull a model. The operator is responsible for installing Ollama and making the configured local model available before enabling this mode.

### Local-only enforcement

The provider boundary is intentionally stricter than a generic OpenAI-compatible client:

- `base_url` must use plain HTTP on `127.0.0.1`, `::1`, or `localhost`.
- Credentials, URL paths, queries and fragments are rejected in the configured origin.
- Before every request the hostname is resolved again; every resolved address must be loopback.
- System HTTP proxies are disabled for local AI requests.
- Ollama model names/tags containing `cloud` are rejected in local-only mode.
- No cloud-provider fallback exists.
- No model is automatically downloaded.

## Data sent to the local model

The advisory context is deliberately bounded and structured. It may contain:

- target and mission state;
- Target Profile kind / complexity / ports / services / technologies / unknowns;
- evidence-linked hypothesis summaries;
- Evidence Confidence claim states and Fact references;
- currently planned governed capability names, risk and approval requirement;
- up to 64 Intelligence Fact summaries and IDs;
- when adaptive ranking is active, summaries of **already-eligible** Capability Catalog candidates: tool identifier, deterministic score/reasons, semantic provides/requires/resolves fields, risk and approval requirement.

TONMEN does **not** put raw tool `argv`, raw `stdout`, raw `stderr`, or candidate execution parameters into the local advisory context.

The local model returns structured JSON only. Any Fact ID returned by the model is filtered against Fact IDs that already exist in the mission graph. Any capability preference naming a tool that was not supplied as an eligible candidate is discarded.

## Authority boundary

Local AI is an **analysis advisor**, not an executor.

An `ai.advisory` node may contain:

- evidence analysis summary;
- areas that deserve additional review;
- evidence-linked hypotheses;
- a challenge to the current analytical interpretation when a deterministic decision actually exists;
- basis Fact IDs;
- bounded preferences over already-eligible Capability Catalog candidates.

It cannot:

- create or submit shell commands;
- create raw adapter argv or parameters;
- register a new tool;
- make an ineligible candidate eligible;
- expand Scope;
- issue or consume Approval grants;
- change risk classification;
- bypass REPORT_ONLY;
- execute payloads;
- capture credentials;
- take over sessions;
- create persistence.

`execution_authority=false` is written by TONMEN code, not trusted from model output.

## Capability preference tie-break

Candidate preference is deliberately weaker than deterministic planning.

The sequence is:

1. Capability Catalog evaluates target/profile prerequisites, semantic prerequisites, typed adapter validation, Policy and readiness.
2. Catalog computes deterministic candidate scores.
3. Only eligible candidate summaries are sent to Local AI.
4. Local AI may return `tool`, preference `[-1, 1]`, rationale and existing Fact IDs.
5. TONMEN applies the preference only if the candidate is within **5.0 deterministic score points** of the deterministic winner.
6. The maximum AI adjustment is **±2.5 score points**.
7. Final selection still consists exclusively of catalog-eligible candidates.

A candidate outside that deterministic tie-break window receives zero AI adjustment. A Policy-denied, unready, out-of-scope or otherwise ineligible candidate cannot be revived by the model.

The `planning.revision` audit records deterministic score, candidate rankings, AI preference, bounded adjustment, final score and selection engine. See `docs/CAPABILITY_CATALOG.md` for the complete planning contract.

## Deterministic fallback

If the local provider is unavailable, times out, returns invalid JSON, or otherwise fails, TONMEN records `ai.advisory_error` with `fallback=deterministic` and continues through the existing deterministic Planner / Reasoner / Policy / Approval path.

A local-model outage therefore does not turn into an execution failure and does not weaken governance.

## Provenance

Successful advisory output is stored as an `ai.advisory` Evidence Graph node. Existing Facts linked by the advisory basis are connected with `supports_ai_advisory` edges. Provider errors are stored as `ai.advisory_error` nodes.

When capability preferences are present, the advisory node also stores the candidate set and filtered preferences. The subsequent `planning.revision` stores the bounded effect of that advisory on ranking.

The model output remains advisory provenance only. Deterministic Scope / Policy / Approval / typed Adapter / Executor components remain the only execution authority.
