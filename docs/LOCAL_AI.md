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
- bounded DNS address summaries;
- bounded negotiated TLS-version and certificate-SAN summaries;
- evidence-linked hypothesis summaries;
- Evidence Confidence claim states and Fact references;
- currently planned governed capability names, risk and approval requirement;
- bounded Catalog candidate summaries for tie-break review;
- up to 64 Intelligence Fact summaries and IDs.

TONMEN does **not** put raw tool `argv`, raw `stdout`, raw `stderr`, raw TLS certificate bytes, candidate execution parameters, credentials, or session values into the local advisory context.

The local model returns structured JSON only. Any Fact ID returned by the model is filtered against Fact IDs that already exist in the mission graph. Any candidate tool ID is filtered against the already-eligible Catalog candidate whitelist.

## Authority boundary

Local AI is an **analysis advisor**, not an executor.

An `ai.advisory` node may contain evidence analysis summary, review focus, evidence-linked hypotheses, a decision-review challenge when a deterministic decision actually exists, basis Fact IDs, and bounded candidate preferences.

It cannot:

- create or submit shell commands;
- create raw adapter argv;
- register a new tool;
- expand Scope;
- issue or consume Approval grants;
- change risk classification;
- bypass REPORT_ONLY;
- execute payloads;
- capture credentials;
- take over sessions;
- create persistence.

`execution_authority=false` is written by TONMEN code, not trusted from model output.

## Bounded candidate preference

When the deterministic Capability Catalog has more than one already-eligible candidate, local AI may express a preference in `[-1, 1]` over only those supplied candidate IDs.

This is a tie-break signal, not selection authority:

- candidates outside 5.0 deterministic-score points of the deterministic winner receive no AI adjustment;
- maximum adjustment is ±2.5 points;
- ineligible, Policy-denied, or unready candidates cannot be revived;
- the model cannot alter candidate parameters, risk, approval status, Scope or Policy.

The resulting `planning.revision` persists the deterministic score, preference, bounded adjustment, final score and selection engine.

## Deterministic fallback

If the local provider is unavailable, times out, returns invalid JSON, or otherwise fails, TONMEN records `ai.advisory_error` with `fallback=deterministic` and continues through the existing deterministic Planner / Reasoner / Policy / Approval path.

A local-model outage therefore does not turn into an execution failure and does not weaken governance.

## Provenance

Successful advisory output is stored as an `ai.advisory` Evidence Graph node. Existing Facts linked by the advisory basis are connected with `supports_ai_advisory` edges. Provider errors are stored as `ai.advisory_error` nodes.

The model output remains advisory provenance only. Deterministic Scope / Policy / Approval / typed Adapter / Executor components remain the only execution authority.
