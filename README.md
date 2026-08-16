# 雲頂天宮 | S̶h̶e̶l̶l̶

> **雲上有宮，宮中有門。門非為人而開，乃為意志而啟。**

**TONMEN** is the autonomous security-agent runtime by **Top-Men AI**.

TONMEN now separates **planning** from **execution**: intent is turned into a visible mission plan only after target scope is accepted. The planner cannot bypass policy, cannot issue approvals, and does not execute tools while planning.

> **谋定而后动，知止而有得。**

## Command milestone

```text
Intent
  ↓
天機 Mission Planner   ← dry-run planning only
  ↓
天域 Scope
  ↓
天律 Policy
  ↓
Mission Steps
  ├─ Nmap    [discovery]
  ├─ HTTPx   [discovery]
  └─ Nuclei  [waiting approval]
  ↓
Observation / Evidence Graph
```

### CLI

```bash
# governed runtime status
tonmen status

# plan only; default scope is localhost
tonmen plan localhost
```

Planning an out-of-scope target is denied. `plan` does not invoke Nmap, HTTPx or Nuclei and does not write an execution audit event.

### Current safety invariants

- External targets remain denied by default.
- No arbitrary shell API exists.
- Execution uses adapter argv with `shell=False`.
- Validation/intrusive actions require a bound, single-use approval grant.
- MCP cannot self-approve.
- Planner only consumes capabilities already governed by Sentinel.

> **器随心转，术因势生；然无律之器，不入天宮。**

## Next

Next comes the **Mission Coordinator**: it will execute only autonomous discovery steps inside scope, pause at approval boundaries, convert results into observations, and attach evidence to the provenance graph. No validation step will cross its approval gate automatically.
