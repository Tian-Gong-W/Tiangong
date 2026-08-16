# 雲頂天宮 | S̶h̶e̶l̶l̶

> **雲上有宮，宮中有門。門非為人而開，乃為意志而啟。**

**TONMEN** is the governed autonomous security-agent runtime by **Top-Men AI**.

TONMEN turns authorized intent into a visible mission plan, executes only autonomous discovery steps inside scope, records evidence and observations, and stops at approval boundaries before higher-risk validation.

> **人予其意，宮成其事；事有所止，止於天律。**

## Mission Coordinator

```text
Intent
  ↓
天機 Mission Planner
  ↓
天域 Scope
  ↓
天律 Policy
  ↓
天命 Mission Coordinator
  ├─ Nmap    → execute → evidence → observation
  ├─ HTTPx   → execute → evidence → observation
  └─ Nuclei  → WAITING APPROVAL
                  ↓ human grant only
               resume
                  ↓
              execute safely
```

The plan remains immutable. Runtime state lives in a separate `MissionRun`, so execution can pause at an approval boundary and resume without repeating completed discovery steps.

### CLI

```bash
# governed runtime status
tonmen status

# dry-run only
tonmen plan localhost

# execute autonomous in-scope discovery; stops before validation
tonmen run localhost
```

The default target scope remains localhost-only. External targets are denied unless they are explicitly configured into the authorized scope.

### Current safety invariants

- No arbitrary shell API exists.
- Adapter execution always uses structured argv with `shell=False`.
- External targets are deny-by-default.
- Unknown tool parameters are rejected.
- Validation/intrusive actions require a bound, single-use approval grant.
- Mission Coordinator never issues its own approval.
- Completed discovery steps are not replayed when a paused mission resumes.
- Every successful step is connected to evidence and an observation in the provenance graph.

> **谋而后行，行而有据；力有所界，智有所止。**
