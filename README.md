# 雲頂天宮 | S̶h̶e̶l̶l̶

> **人予其意，宮成其事。**  
> **宮察其象，鑑明其實；天策既定，萬器乃行。**

**TONMEN** is the governed autonomous security-agent runtime by **Top-Men AI**.

TONMEN now separates intent, execution, evidence, knowledge, and decision. Tools do not decide what is true; deterministic intelligence parsers turn raw evidence into provenance-linked facts, and **天策 · Reasoner** decides only from those facts and the existing governed mission plan.

## Tiance / 天策

```text
Intent
  ↓
天機 Planner
  ↓
天域 Scope + 天律 Policy
  ↓
天命 Coordinator
  ↓
天工 Executor
  ↓
Evidence
  ↓
天鑑 Intelligence
  ↓
天策 Reasoner
  ├─ CONTINUE          continue an already-planned low-risk step
  ├─ REQUEST_APPROVAL  stop at a human approval boundary
  ├─ SKIP              avoid unjustified higher-risk validation
  ├─ REVIEW            surface high/critical findings to a human
  ├─ COMPLETE          stop when current evidence justifies no more work
  └─ STOP              halt after failure or denial
```

Every reasoning decision is written into the same Evidence Graph used by Chronicle. Facts link to decisions with `supports_decision`; decisions can point only to an existing mission step. There is no free-form command generation in the Reasoner.

### A deliberately asymmetric authority model

天策 may **stop** or **skip** automatically, but it may not grant itself more authority.

For the current Nmap → HTTPx → Nuclei mission:

- confirmed web/service evidence may justify asking a human to approve Nuclei;
- absence of evidence-backed web surface causes Nuclei to be skipped automatically;
- approval remains a fresh, single-use grant bound to the exact tool and target;
- high/critical findings produce a human-review decision, not an automatic escalation.

> **可代人止，不可代人越。**

### CLI

```bash
tonmen status
tonmen plan localhost
tonmen run localhost

tonmen missions
tonmen show <run-id>

# explain what 天策 currently decides and why
tonmen reason <run-id>

# crossing an approval boundary still requires an explicit human act
tonmen resume <run-id> --approve
```

The default authorized scope remains localhost-only.

## Current invariants

- No arbitrary shell API.
- Structured adapter argv only; Executor enforces `shell=False`.
- External targets deny-by-default.
- Unknown tool parameters are rejected.
- Validation/intrusive actions require a bound, single-use grant.
- Planner, Coordinator, Intelligence and Reasoner cannot self-approve.
- Approval tokens are never persisted.
- Intelligence facts must point to Evidence IDs.
- Unparseable output remains evidence; it does not become a guessed fact.
- Reasoner can recommend only existing mission steps.
- Reasoning decisions and their fact basis persist through Chronicle.

> **所知必有據，所斷必有源；能止其鋒，方可久行。**
