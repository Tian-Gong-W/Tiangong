# 雲頂天宮 | S̶h̶e̶l̶l̶

> **雲上有宮，宮中有門。門非為人而開，乃為意志而啟。**

**TONMEN** is the governed autonomous security-agent runtime by **Top-Men AI**.

TONMEN now does more than execute authorized tools: **天鑑 Intelligence** deterministically interprets evidence into provenance-linked facts. It does not guess from raw output and does not use an LLM to invent findings.

> **宮，不但能行，而且能知；所知必有據，所斷必有源。**

## Intelligence / 天鑑

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
Raw Evidence
  ↓
天鑑 Deterministic Parsers
  ├─ Nmap   → host / service facts
  ├─ HTTPx  → web endpoint facts
  └─ Nuclei → vulnerability findings
  ↓
Observation
  ↓
Evidence Graph
  ↓
天冊 Chronicle
```

Every intelligence node stores its source tool, target, confidence, evidence ID and structured data. Evidence Graph remains the single provenance store, so intelligence survives Chronicle persistence without introducing a second competing knowledge database.

### CLI

```bash
# governed runtime status
tonmen status

# plan only
tonmen plan localhost

# execute in-scope discovery; parsed intelligence is shown in the run output
tonmen run localhost

# inspect persisted knowledge later
tonmen missions
tonmen show <run-id>

# approval boundary remains explicit
tonmen resume <run-id>
tonmen resume <run-id> --approve
```

Example shape:

```text
天鑑所見
  · host    Host observed: localhost
  · service 80/tcp open http (nginx 1.24.0)
  · web     https://localhost [200] Welcome
  · finding [high] Demo Exposure
```

### Current invariants

- No arbitrary shell API.
- Structured adapter argv only; Executor enforces `shell=False`.
- External targets deny-by-default.
- Validation/intrusive actions require a bound, single-use grant.
- Planner and Coordinator cannot self-approve.
- Approval tokens are never persisted.
- Raw stdout/stderr remains the source evidence.
- Intelligence facts must point back to an Evidence ID.
- Unparseable output remains evidence; TONMEN does not manufacture a fact merely to fill a result.
- Chronicle persists the Evidence Graph, including intelligence provenance.

> **见一叶而知秋，察一隙而知危；然无据之言，不录于鑑。**
