# 雲頂天宮 | S̶h̶e̶l̶l̶

> **雲上有宮，宮中有門。門非為人而開，乃為意志而啟。**

**TONMEN** is the governed autonomous security-agent runtime by **Top-Men AI**.

TONMEN turns authorized intent into a visible mission, executes only in-scope autonomous discovery, records raw evidence and observations, pauses before higher-risk validation, and persists that state so a human can explicitly resume it later.

> **人予其意，宮成其事；事有所止，止於天律。**

## Chronicle / 天冊

```text
Intent
  ↓
天機 Planner
  ↓
天域 Scope + 天律 Policy
  ↓
天命 Coordinator
  ├─ discovery → evidence → observation
  └─ validation → 候旨 / WAITING_APPROVAL
                    ↓
              天冊 Chronicle
             plan + run + evidence
                    ↓
              human --approve
                    ↓
                resume only
```

Mission plans and runtime state are separate. Completed discovery steps are never replayed merely because the process restarted.

Chronicle stores mission files under the TONMEN workspace with restrictive local permissions where the operating system supports them. Approval tokens are intentionally never persisted.

### CLI

```bash
# runtime status
tonmen status

# dry-run only
tonmen plan localhost

# execute safe discovery and persist the resulting mission
tonmen run localhost

# list/show persisted runs
tonmen missions
tonmen show <run-id>

# show the approval boundary without crossing it
tonmen resume <run-id>

# explicit human approval of the current waiting step, then resume
tonmen resume <run-id> --approve
```

The default scope remains localhost-only. External targets are denied unless explicitly configured into the authorized scope.

### Current invariants

- No arbitrary shell API.
- Structured adapter argv only; Executor enforces `shell=False`.
- External targets deny-by-default.
- Unknown tool parameters are rejected.
- Validation/intrusive actions require a bound, single-use grant.
- Planner and Coordinator cannot self-approve.
- Approval tokens are not written to Chronicle.
- Mission persistence rejects unsafe/path-traversal run IDs.
- Raw stdout/stderr evidence survives pause/restart and remains linked to observations.

> **谋而后行，行而有据；事可暂止，志不可失。**
