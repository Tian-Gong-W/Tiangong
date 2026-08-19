# Lead AI Orchestrator

TONMEN can optionally place one **Lead AI** above the bounded Assessment Council.

The hierarchy is:

```text
Mission
  -> Lead AI directive
      -> Council round
          -> 3-5 evidence-only subagents
```

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

## Secret handling

The API key is deliberately **not** part of `TonmenConfig`. TONMEN reads the secret
environment variable only when the provider sends a server-side request.

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

The first Lead AI integration sends a bounded structured snapshot only:

- mission target/state/round
- planned tool names, targets, risk and step state
- Evidence IDs, tool names, exit codes and stdout/stderr byte counts
- Intelligence fact IDs, labels, severity, confidence and Evidence IDs

Raw stdout/stderr, raw request/response payloads and Approval tokens are **not** sent
to the Lead AI in this version.

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
