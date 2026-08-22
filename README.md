# 雲頂天宮 | S̶h̶e̶l̶l̶

> **人予其意，宮成其事。**  
> **宮察其象，鑑明其實；天策既定，萬器乃行。**

**TONMEN** is the governed autonomous security-agent runtime by **Top-Men AI**.

**v0.4.0 Alpha** includes project configuration, persistent authorized scope, dependency diagnostics, bounded mission loops, evidence-backed intelligence, explicit human approval boundaries, a local visual control panel, and the first adaptive-research runtime primitives.

## Install

Requires Python **3.10+** plus Nmap (`nmap`), ProjectDiscovery HTTPx (`httpx`) and ProjectDiscovery Nuclei (`nuclei`).

```bash
git clone https://github.com/Top-Men-AI/TONMEN.git
cd TONMEN
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .

tonmen doctor
tonmen init
tonmen scope show
```

## Visual Console / 可視控制面板

Launch the real local TONMEN dashboard:

```bash
tonmen console
```

It opens **雲頂天宮 Console** on `http://127.0.0.1:8888/`. The panel reads and controls the same governed runtime as the CLI: status, Scope, missions, Chronicle, Intelligence, Reasoner decisions, Evidence Graph, raw Evidence, bounded resume, and the human Approval Gate.

```bash
tonmen console --port 8899
tonmen console --no-open
tonmen --config /path/to/tonmen.toml console
```

The Console is loopback-only. State-changing browser requests require a per-process CSRF token; approval still uses the existing single-use Tool + Target Grant. See **[Console Guide](docs/CONSOLE.md)**.

## Authorize a target

TONMEN remains **deny-by-default**. Loopback is always authorized; external assets must be explicitly added to the project configuration.

```bash
tonmen scope add app.example.test
tonmen scope add 10.20.30.0/24
tonmen scope add '*.example.test'
tonmen scope show
```

Only add targets you own or are explicitly authorized to assess. The same rules can be managed from **天域 Scope** in the visual Console.

## Plan, then run

```bash
tonmen plan app.example.test
tonmen loop app.example.test
```

The current CLI path remains the compatibility runtime while the Console/Chronicle migrate to adaptive state:

```text
Intent
  ↓
天機 Planner
  ↓
天域 Scope + 天律 Policy
  ↓
天衡 Mission Loop
  ↓
天命 Coordinator → 天工 Executor
  ↓
Evidence → 天鑑 Intelligence → 天策 Reasoner
  ↓
CONTINUE / SKIP / COMPLETE / REQUEST_APPROVAL / REVIEW / STOP
```

The compatibility plan still exposes Nmap → HTTPx → Nuclei so existing CLI, Chronicle and reports remain stable. Discovery may run inside authorized scope. Nuclei validation remains approval-gated.

```bash
tonmen missions
tonmen show <run-id>
tonmen reason <run-id>
tonmen resume <run-id> --approve
```

Approval tokens are never persisted.

## Adaptive research core

The new research path does **not** pre-generate the entire future mission. It starts with a minimum bootstrap experiment, then regenerates candidate actions from the current hypotheses, evidence, previous action signatures, Scope and Policy.

```text
Mission goal
  ↓
Hypothesis
  ↓
bootstrap (minimum useful action)
  ↓
AdaptiveMissionDirector
  ↓
decide_next(current state)
  ↓
ActionProposal candidates
  ↓
Scope / Policy / Approval
  ↓
Executor
  ↓
Evidence + ActionLedger
  ↺ re-plan from the new state
```

Core primitives now include:

- `CapabilitySpec`: semantic planner-facing capability contract layered over legacy `ToolSpec`.
- `Hypothesis` + `EvidenceRequirement`: explicit research questions that can later be supported, rejected or confirmed by evidence requirements.
- `ActionProposal`: a newly-created experiment with information-gain, relevance, cost, risk and replayability metadata.
- `AdaptiveMissionState` + `ActionRecord`: append-only research state and action ledger.
- `MissionPlanner.bootstrap()` + `MissionPlanner.decide_next()`: minimum bootstrap followed by state-driven re-planning with duplicate-action suppression.
- `AdaptiveMissionDirector.tick()`: executes one selected action at a time through the existing governed Runtime path.

The adaptive Director can create **new ActionProposals after a mission has started**, but it cannot register arbitrary tools, expand Scope, bypass Policy, mint approvals, or execute raw shell strings. Higher-risk work still stops at the existing Approval boundary.

## Project config

Create `tonmen.toml` with `tonmen init`, or start from [`tonmen.toml.example`](tonmen.toml.example). See **[Getting Started](docs/GETTING_STARTED.md)** for the complete first-run flow.

## Current invariants

- No arbitrary shell API.
- Structured adapter argv only; Executor enforces `shell=False`.
- External targets deny-by-default.
- Unknown tool parameters are rejected.
- Validation/intrusive actions require a bound, single-use grant.
- Planner, Director, Coordinator, Intelligence, Reasoner and Mission Loop cannot self-approve.
- Adaptive planning may create new ActionProposals only from registered capabilities; it cannot expand target scope or register arbitrary executors.
- The legacy Mission Loop cannot add tools or expand target scope.
- Approval tokens are never persisted.
- Intelligence facts must point to Evidence IDs.
- Unparseable output remains evidence; it does not become a guessed fact.
- Every loop session has bounded iterations, executions, duration and repeat tolerance.
- Reasoning and loop-governance provenance persist through Chronicle.
- Visual Console is loopback-only and cannot bypass Scope, Policy or Approval.

> **所知必有據，所斷必有源；萬器可行，必先有衡。**

TONMEN is intended for authorized security testing and defensive research.
