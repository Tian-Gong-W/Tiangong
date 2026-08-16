# 雲頂天宮 | S̶h̶e̶l̶l̶

> **雲上有宮，宮中有門。門非為人而開，乃為意志而啟。**

**TONMEN** is the autonomous security-agent runtime by **Top-Men AI**.

Traditional shells wait for commands. TONMEN receives intent, resolves an authorized plan, selects registered capabilities, enforces policy, executes typed adapters, and records evidence.

> **人定其志，器循其道。自主而有界，言必有據，行必有跡。**

## Forge milestone

Forge establishes TONMEN's first guarded execution loop:

```text
ToolRequest
   ↓
天工 Registry
   ↓
天律 Policy
   ↓
Typed Adapter
   ↓
天行 Executor (shell=False)
   ↓
天錄 Evidence
   ↓
Job Result
```

Built-in adapters in this milestone:

- **Nmap** — conservative TCP connect/service discovery (`DISCOVERY`)
- **HTTPx** — HTTP metadata and technology discovery (`DISCOVERY`)
- **Nuclei** — bounded vulnerability validation (`VALIDATION`, explicit approval required)

## Security invariants

1. No arbitrary shell API in the TONMEN core.
2. Adapters produce argv sequences; execution always uses `shell=False`.
3. Unknown adapter parameters are rejected rather than appended to commands.
4. Validation/intrusive capabilities require approval; destructive capabilities remain disabled.
5. Raw stdout/stderr, argv, timestamps, target and exit code are represented as evidence.
6. MCP exposes the capability catalog only in Forge; remote execution will not be exposed until scope and authorization are implemented.

> **力可破山，律可束力。无律之强，不过狂锋；有界之智，方可久行。**

## Install

```bash
python -m pip install -e .
tonmen
```

Expected banner:

```text
雲頂天宮 | TONMEN Forge
天樞 Core        ● Online
天律 Guard       ● Online
天工 Registry    ● Ready (3 tools)
天行 Executor    ● Ready
天錄 Evidence    ● Ready
天機 Agent       ○ Not loaded

人予其意，宮成其事。
```

## Next

The next milestone is **Sentinel / 天律篇**: explicit target scopes, approval grants, persistent audit records, and a guarded MCP execution surface. Autonomous planning comes only after those controls exist.
