# 雲頂天宮 | S̶h̶e̶l̶l̶

> **雲上有宮，宮中有門。門非為人而開，乃為意志而啟。**

**TONMEN** is the autonomous security-agent runtime by **Top-Men AI**.

Traditional shells wait for commands. TONMEN receives intent, checks authorized scope, applies risk policy, validates approvals, executes typed adapters, and records evidence plus an append-only audit trail.

> **人定其志，器循其道。自主而有界，言必有據，行必有跡。**

## Sentinel milestone

Sentinel turns Forge's execution loop into a governed runtime:

```text
Intent / MCP request
        ↓
天域 Target Scope
        ↓
天律 Risk Policy
        ↓
天契 Approval Grant  ← required for validation/intrusive actions
        ↓
天工 Typed Adapter
        ↓
天行 Executor (shell=False)
        ↓
天錄 Evidence + Audit
```

### Default posture

- External targets are **denied by default**; the default scope contains localhost only.
- Scope supports exact hosts/IPs, wildcard subdomains, and CIDRs; deny rules override allow rules.
- Approval grants are short-lived, single-use, and bound to one tool + exact target.
- MCP can submit guarded jobs but **cannot issue its own approval grants**.
- Destructive capabilities remain denied.
- No arbitrary shell API exists in the TONMEN core.

Built-in adapters remain deliberately small:

- **Nmap** — conservative TCP connect/service discovery (`DISCOVERY`)
- **HTTPx** — HTTP metadata and technology discovery (`DISCOVERY`)
- **Nuclei** — bounded vulnerability validation (`VALIDATION`, approval required)

> **力可破山，律可束力。无律之强，不过狂锋；有界之智，方可久行。**

## Install

```bash
python -m pip install -e .
tonmen
```

Expected banner:

```text
雲頂天宮 | TONMEN Sentinel
天樞 Core        ● Online
天律 Guard       ● Online
天工 Registry    ● Ready (3 tools)
天域 Scope       ● Enforced
天契 Approval    ● Ready
天錄 Audit       ● Persistent
天行 Executor    ● Ready
天機 Agent       ○ Not loaded

人予其意，宮成其事。
```

## Security model

See `SECURITY.md`. TONMEN is designed for authorized assessment and defensive research. Operators must explicitly configure non-local targets they are authorized to assess.

## Next

The next milestone is **Command / 天機篇**: mission planning, observations, evidence graphing, and a human-visible control surface. Planning will consume only capabilities already governed by Sentinel.
