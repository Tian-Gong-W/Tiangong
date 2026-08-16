# 雲頂天宮 | S̶h̶e̶l̶l̶

> **人予其意，宮成其事。**  
> **宮察其象，鑑明其實；天策既定，萬器乃行。**

**TONMEN** is the governed autonomous security-agent runtime by **Top-Men AI**.

TONMEN now has a bounded mission loop: evidence is observed, deterministic intelligence is extracted, 天策 decides from that evidence, and 天衡 determines whether one more already-planned governed action may run. The loop may stop itself automatically; it may never grant itself more authority.

## Tianheng / 天衡

```text
Intent
  ↓
天機 Planner
  ↓
天域 Scope + 天律 Policy
  ↓
┌────────────── 天衡 Mission Loop ──────────────┐
│                                               │
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
│          │                                    │
└──────────┴──────── one bounded step ──────────┘
```

### Boundaries before autonomy

A loop session has explicit, validated limits:

- `max_iterations` — default 8, hard maximum 64;
- `max_executions` — default 3, hard maximum 16;
- `max_repeat_decisions` — default 2, hard maximum 8;
- `max_duration_seconds` — default 300, hard maximum 3600.

Loop governance is written into the existing Evidence Graph as `loop.session`, `loop.iteration`, and `loop.stop` nodes, so Chronicle persists not only what happened, but why the autonomous cycle stopped.

> **衡者，度也。知其可行，亦知其當止。**

### Authority remains asymmetric

天衡 may:

- execute another already-planned step that is still allowed by Scope and Policy;
- stop on execution or time budget exhaustion;
- stop repeated no-progress reasoning;
- apply a 天策 `SKIP` decision to avoid unsupported higher-risk validation;
- stop for human review or approval.

天衡 may not:

- add a tool that was not already in the governed mission plan;
- expand target scope;
- create arbitrary command strings;
- issue an Approval Grant;
- persist an approval token;
- cross `REQUEST_APPROVAL` without a fresh human-issued grant.

For the current Nmap → HTTPx → Nuclei mission, confirmed web evidence causes the loop to stop at the Nuclei approval boundary. If no evidence-backed web surface exists, 天策 may skip Nuclei and 天衡 can safely complete the loop without running it.

### CLI

```bash
tonmen status
tonmen plan localhost

# legacy run-to-boundary behavior
tonmen run localhost

# bounded observe → reason → act loop
tonmen loop localhost

# optional tighter budgets
tonmen loop localhost --max-iterations 6 --max-executions 2

# a budget-stopped RUNNING mission requires an explicit fresh loop session
tonmen loop-resume <run-id>

tonmen missions
tonmen show <run-id>
tonmen reason <run-id>

# approval remains a separate human authority act
tonmen resume <run-id> --approve
```

The default authorized scope remains localhost-only.

## Current invariants

- No arbitrary shell API.
- Structured adapter argv only; Executor enforces `shell=False`.
- External targets deny-by-default.
- Unknown tool parameters are rejected.
- Validation/intrusive actions require a bound, single-use grant.
- Planner, Coordinator, Intelligence, Reasoner and Mission Loop cannot self-approve.
- Approval tokens are never persisted.
- Intelligence facts must point to Evidence IDs.
- Unparseable output remains evidence; it does not become a guessed fact.
- Reasoner can recommend only existing mission steps.
- Mission Loop can execute only existing mission steps.
- Every loop session has bounded iterations, executions, duration and repeat tolerance.
- Reasoning and loop-governance provenance persist through Chronicle.

> **所知必有據，所斷必有源；萬器可行，必先有衡。**
