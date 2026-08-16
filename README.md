# 雲頂天宮 | S̶h̶e̶l̶l̶

> 雲上有宮，宮中有門。門非為人而開，乃為意志而啟。

**TONMEN** is the autonomous security-agent runtime by **Top-Men AI**.

Traditional shells wait for commands. TONMEN receives intent, resolves an authorized plan, selects registered capabilities, enforces scope and policy, and records evidence before execution.

> 人定其志，器循其道。自主而有界，言必有據，行必有跡。

## Genesis principles

1. **No arbitrary shell API in the new core.** Tools are invoked through typed adapters.
2. **Policy before execution.** Every action receives an explicit risk and decision.
3. **Registry as the source of truth.** Agents discover capabilities through the registry.
4. **Legacy is migration input, not architecture.** Existing HexStrike-derived capabilities may be migrated selectively without inheriting its architecture.
5. **Evidence-first design.** Every future execution result must be traceable to request, policy decision, adapter, and raw evidence.

## Package map

```text
src/tonmen/
├── core/      # 天樞 · runtime and configuration
├── tools/     # 天工 · typed tool adapters and registry
├── policy/    # 天律 · risk and authorization decisions
└── mcp/       # MCP-facing boundary (no direct shell execution)
```

## Install and run

```bash
python -m pip install -e .
tonmen
```

Expected Genesis banner:

```text
雲頂天宮 | TONMEN Genesis
天樞 Core        ● Online
天律 Guard       ● Online
天工 Registry    ● Ready
天機 Agent       ○ Not loaded

人予其意，宮成其事。
```

## Roadmap

Genesis establishes the independent TONMEN core. The next milestone will introduce the first typed tool adapters, job runtime, evidence model, and guarded MCP execution flow.
