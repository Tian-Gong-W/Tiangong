# Local model runtime

TONMEN can run in two modes:

- **Deterministic mode** (default): no model and no API key.
- **Local Agent mode**: a loopback Ollama model supplies read-only structured subagent reviews. No cloud API key is required.

The model runtime is optional. Scope, Policy, Approval, typed ToolAdapters, execution budgets and the mandatory REPORT_ONLY gate remain authoritative in both modes.

## Local Ollama setup

Install and start Ollama, then make sure the model you want to use is already available locally. TONMEN does not automatically download models.

Configure the current shell before starting TONMEN:

```bash
export TONMEN_MODEL_PROVIDER=ollama
export TONMEN_MODEL_NAME=qwen3
export TONMEN_MODEL_BASE_URL=http://127.0.0.1:11434/api
export TONMEN_MODEL_TIMEOUT=60
export TONMEN_MODEL_MAX_CALLS=50
```

`TONMEN_MODEL_MAX_CALLS` is limited to 1-50. Fifty is the absolute ceiling corresponding to 10 assessment rounds × 5 subagents. Lower values are allowed; once the budget is exhausted, remaining roles fall back to deterministic evidence review.

Unset `TONMEN_MODEL_PROVIDER` (or set it to `none`) to return to deterministic mode.

## Security properties

The local provider intentionally has a narrow transport boundary:

- only `http://localhost`, `http://127.0.0.1` or loopback IPv6 may be configured;
- proxy use is disabled for model requests;
- redirects are rejected;
- no API key is read or sent for local mode;
- only a bounded Target Profile is sent to the model, not arbitrary workspace files;
- model responses must match a JSON schema;
- recommendations are filtered against the mission's existing candidate capability identifiers;
- model tool/function calling is not exposed;
- model output has no execution authority;
- credential capture, session takeover, persistence and final active actions remain prohibited by Policy/REPORT_ONLY.

## What becomes a real model subagent

When local Agent mode is enabled, each dynamic Council role performs its own structured model review. A review may contain:

- summary;
- evidence-oriented observations;
- risk questions;
- unresolved questions;
- up to three recommendations from the already-governed capability allowlist;
- confidence and token accounting.

The model does **not** return argv, shell commands or approval decisions. Its proposals remain advisory until deterministic TONMEN components accept or reject them.

## Failure behavior

If Ollama is unavailable, the selected model is missing, a response is malformed, or the call budget is exhausted, TONMEN records the model error and continues that role using deterministic analysis. A model outage therefore cannot remove governance or block report generation.
