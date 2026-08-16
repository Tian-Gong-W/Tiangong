# 雲頂天宮 Console

TONMEN Console is the local web control surface for the governed runtime.

It is not a separate execution engine. The panel calls the same Planner, Scope, Policy, Mission Loop, Chronicle, Intelligence and Approval components used by the CLI.

## Start

```bash
python -m pip install -e .
tonmen console
```

The console binds to `127.0.0.1` only and opens:

```text
http://127.0.0.1:8888/
```

Use another local port if required:

```bash
tonmen console --port 8899
```

Do not open a new browser automatically:

```bash
tonmen console --no-open
```

With another project config:

```bash
tonmen --config /path/to/tonmen.toml console
```

## What the panel controls

The dashboard provides live views for runtime health, persistent authorized Scope, Chronicle mission history, governed mission steps, Evidence-backed Intelligence, Reasoner decisions, Mission Loop stop state, raw Evidence inspection and explicit Approval Gate actions.

The panel can add/remove non-default authorized Scope rules, start a bounded mission for an authorized target, resume a budget-stopped mission, and explicitly approve the exact waiting Tool + Target step.

## Security properties

- The Console entry point binds only to `127.0.0.1`.
- `0.0.0.0` and external interfaces are rejected by the server helper.
- State-changing requests require an in-memory per-process CSRF token.
- Cross-origin write requests are rejected and no CORS allowance is sent.
- CSP, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, and no-referrer headers are set.
- The panel cannot add arbitrary commands or bypass Registry / Policy / Scope.
- Approval still creates a fresh single-use Grant bound to the waiting Tool + Target.
- Approval tokens remain in memory and are never persisted.

Stopping the Console process destroys its CSRF token and any in-memory Approval Grants.

> 人予其意，宮成其事。  
> 宮察其象，鑑明其實；天策既定，萬器乃行。
