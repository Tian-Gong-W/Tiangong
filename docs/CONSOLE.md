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

## Overview + detailed workspaces

The root page `/` is the command overview. It keeps the current mission, Command Deck, Scope summary, Intelligence summary, Reasoner decision, Approval Gate, Chronicle and Evidence Graph in one place for fast operations.

Each major capability also has its own detailed workspace:

```text
/                  Overview / Command Deck
/missions          Mission history, steps, argv, stdout/stderr, retry/resume
/scope             Full authorized/denied target management
/guard             Risk policy, approval boundaries and live audit
/tools             Registry tools, installation state, risk and capabilities
/intelligence      Evidence-backed facts across recent missions
/reasoner          Reasoning decisions, Fact basis and next-step links
/loop              Mission Loop sessions, iterations, stops and budgets
/chronicle         Persisted mission history and execution audit timeline
/approval          All waiting approvals with evidence beside the action
/settings          Project configuration and Doctor readiness
```

The detailed workspaces poll current runtime data every few seconds. They do not create a second execution system: actions still use the same Console APIs and the same governed Scope → Policy → Approval → Executor path.

### Real execution content

The Missions workspace shows the persisted execution details for every completed tool call:

- structured argv used by the adapter;
- exit code;
- stdout;
- stderr;
- step state and error;
- Evidence identifiers and related mission state.

Guard and Chronicle expose the append-only audit tail. Intelligence, Reasoner and Loop read directly from the same Chronicle-persisted Evidence Graph, so the detailed pages preserve provenance instead of reconstructing or guessing state.

## What the panel controls

The dashboard can add/remove non-default authorized Scope rules, start a bounded mission for an authorized target, resume a budget-stopped mission, inspect raw Evidence, retry a failed target, and explicitly approve the exact waiting Tool + Target step.

The same common operations remain available from the Overview Command Deck; detailed module pages add deeper inspection and module-specific controls.

## Security properties

- The Console entry point binds only to `127.0.0.1`.
- `0.0.0.0` and external interfaces are rejected by the server helper.
- State-changing requests require an in-memory per-process CSRF token.
- Cross-origin write requests are rejected and no CORS allowance is sent.
- CSP, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, and no-referrer headers are set.
- The panel cannot add arbitrary commands or bypass Registry / Policy / Scope.
- Detailed workspaces use existing governed APIs; they do not add an alternate execution path.
- Approval still creates a fresh single-use Grant bound to the waiting Tool + Target.
- Approval tokens remain in memory and are never persisted.
- Audit APIs expose decisions and Evidence IDs, never Approval Grant tokens.

Stopping the Console process destroys its CSRF token and any in-memory Approval Grants.

> 人予其意，宮成其事。  
> 宮察其象，鑑明其實；天策既定，萬器乃行。