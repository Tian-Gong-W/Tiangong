# 雲頂天宮 | S̶h̶e̶l̶l̶

> **人予其意，宮成其事。**  
> **宮察其象，鑑明其實；天策既定，萬器乃行。**

**TONMEN** is the governed autonomous security-agent runtime by **Top-Men AI**.

**v0.4.0 Alpha** is the first usability baseline: project configuration, persistent authorized scope, dependency diagnostics, bounded mission loops, evidence-backed intelligence, and explicit human approval boundaries are now wired into one CLI.

## Install

Requires Python **3.10+** plus these external command-line tools:

- Nmap (`nmap`)
- ProjectDiscovery HTTPx (`httpx`) — not the Python package with the same name
- ProjectDiscovery Nuclei (`nuclei`)

```bash
git clone https://github.com/Top-Men-AI/TONMEN.git
cd TONMEN

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

Then:

```bash
tonmen doctor
tonmen init
tonmen scope show
```

## Authorize a target

TONMEN remains **deny-by-default**. Loopback is always authorized; external assets must be explicitly added to the project configuration.

```bash
# exact host
tonmen scope add app.example.test

# CIDR
tonmen scope add 10.20.30.0/24

# wildcard subdomains
tonmen scope add '*.example.test'

tonmen scope show
```

Only add targets you own or are explicitly authorized to assess.

## Plan, then run

```bash
# dry-run only
tonmen plan app.example.test

# bounded observe → reason → act loop
tonmen loop app.example.test
```

Current governed path:

```text
Intent
  ↓
天機 Planner
  ↓
天域 Scope + 天律 Policy
  ↓
┌────────────── 天衡 Mission Loop ──────────────┐
│  天命 Coordinator → 天工 Executor             │
│          ↓                                    │
│       Evidence                                │
│          ↓                                    │
│  天鑑 Intelligence                            │
│          ↓                                    │
│    天策 Reasoner                              │
│          ↓                                    │
│  CONTINUE / SKIP / COMPLETE ────────┐         │
│  REQUEST_APPROVAL / REVIEW / STOP ──┴─► STOP  │
└───────────────────────────────────────────────┘
```

The built-in tool path is currently Nmap → HTTPx → Nuclei. Discovery may run inside authorized scope. Nuclei validation remains approval-gated when evidence supports it.

```bash
tonmen missions
tonmen show <run-id>
tonmen reason <run-id>

# crossing an approval boundary requires a fresh explicit human act
tonmen resume <run-id> --approve
```

Approval tokens are never persisted.

## Project config

Create `tonmen.toml` with:

```bash
tonmen init
```

Or start from [`tonmen.toml.example`](tonmen.toml.example).

Use a non-default config:

```bash
tonmen --config /path/to/tonmen.toml doctor
tonmen --config /path/to/tonmen.toml loop app.example.test
```

See **[Getting Started](docs/GETTING_STARTED.md)** for the complete first-run flow.

## Current invariants

- No arbitrary shell API.
- Structured adapter argv only; Executor enforces `shell=False`.
- External targets deny-by-default.
- Unknown tool parameters are rejected.
- Validation/intrusive actions require a bound, single-use grant.
- Planner, Coordinator, Intelligence, Reasoner and Mission Loop cannot self-approve.
- Mission Loop cannot add tools or expand target scope.
- Approval tokens are never persisted.
- Intelligence facts must point to Evidence IDs.
- Unparseable output remains evidence; it does not become a guessed fact.
- Every loop session has bounded iterations, executions, duration and repeat tolerance.
- Reasoning and loop-governance provenance persist through Chronicle.

> **所知必有據，所斷必有源；萬器可行，必先有衡。**

TONMEN is intended for authorized security testing and defensive research.
