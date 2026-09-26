# Lead AI Orchestrator

TONMEN can optionally place one **Lead AI** above its governed mission runtime.

The Lead AI coordinates review focus, objectives, synthesis and recommended next
state. It does **not** receive execution authority.

## Enable OpenAI

Lead AI is disabled by default, even if the current shell already contains an API
key. Enable it explicitly:

```bash
export TONMEN_AI_PROVIDER="openai"
export OPENAI_API_KEY="your-key"
export TONMEN_AI_MODEL="gpt-5.6"

tonmen status
tonmen console
```

Optional settings:

```bash
export TONMEN_AI_TIMEOUT_SECONDS="30"
export TONMEN_OPENAI_BASE_URL="https://api.openai.com/v1"
```

`TONMEN_AI_KEY_ENV` can point at a different server-side environment variable name
if your deployment injects secrets under another name.

## Enable a pinned Mistral custom Agent as Lead

A Mistral Studio Agent can be selected by immutable Agent id + version:

```bash
export TONMEN_AI_PROVIDER="mistral"
export TONMEN_MISTRAL_AGENT_ID="ag_01a02a0f3b857147bda9118a2481a7a1"
export TONMEN_MISTRAL_AGENT_VERSION="1"
export MISTRAL_API_KEY="your-key"

tonmen status
tonmen console
```

Optional settings:

```bash
export TONMEN_AI_TIMEOUT_SECONDS="30"
export TONMEN_MISTRAL_BASE_URL="https://api.mistral.ai/v1"
```

TONMEN first reads the pinned Agent version and reuses its model, instructions and
safe completion parameters. It then performs the Lead decision through Mistral Chat
Completions in JSON mode.

The Agent's `tools` and `handoffs` are intentionally **not inherited**. A custom
Mistral Agent may describe how the Lead should reason, but all real actions still go
through TONMEN's own Capability Registry, Scope, Policy, Approval and Executor.
This prevents an external Agent tool from becoming a second execution plane outside
the Evidence Graph and Chronicle.

`TONMEN_MISTRAL_AGENT_VERSION` is required rather than silently following the latest
Agent revision so a mission's Lead behavior remains reproducible.

## Secret handling

API keys are deliberately **not** part of `TonmenConfig`. TONMEN reads the selected
provider secret only when the server sends a provider request.

The key is never intentionally written to:

- `tonmen.toml`
- Chronicle
- Evidence Graph
- Reports
- Event Bus
- Audit messages
- Console/browser payloads

The Console should show only whether a key is configured, never the key itself.

## Data sent to Lead AI

The Lead AI integration sends a bounded structured snapshot only:

- mission target/state/round
- governed action names, targets, risk and state
- Evidence IDs, tool names, exit codes and stdout/stderr byte counts
- Intelligence fact IDs, labels, severity, confidence and Evidence IDs

Raw stdout/stderr, raw request/response payloads and Approval tokens are **not** sent
to the Lead AI.

## Authority boundary

A Lead directive may recommend only:

- `continue_governed_plan`
- `await_human_approval`
- `review_failure_evidence`
- `finalize_report`
- `stop_for_human_review`

The recommendation is advisory. Scope, Policy, Approval and Executor remain the only
execution authority. Unsupported model actions are rejected and TONMEN falls back
to deterministic orchestration.

If the provider is disabled, missing a key, unavailable, or returns invalid output,
TONMEN continues with the deterministic Lead fallback and the existing governed
mission behavior.
