# TONMEN Binary Intelligence

Binary Intelligence is a **static artifact-analysis subsystem**. It is intentionally separate from network Mission execution and does not receive arbitrary shell or payload authority.

## Hard boundary

The following are invariants, not optional UI settings:

- Artifact bytes are never executed or dynamically loaded.
- The Console accepts raw uploaded bytes only; it does not accept a server filesystem path.
- Console upload limit: **32 MiB**.
- Library hard limit: **128 MiB**.
- Every stored Artifact is SHA-256 content-addressed.
- Reports state `execution_performed=false`.
- Static analysis does not generate or deliver shellcode or ROP chains.
- Static analysis does not create persistence.
- Review signals do not claim vulnerability confirmation.
- Any future disassembly backend must remain static-only and bounded.

## Intake and provenance

### CLI

```text
tonmen artifact inspect <path>
tonmen artifact list
tonmen artifact show <sha256>
tonmen artifact delete <sha256>
```

Path-based intake is local CLI functionality only. The inspector rejects symbolic links and non-regular files and applies the configured byte ceiling before analysis.

### Console

The `/artifacts` workspace uploads `application/octet-stream` bytes under the existing local Console CSRF boundary. The filename header is display metadata only; only its basename enters the report. A JSON payload such as `{ "path": "/tmp/sample" }` is not an Artifact-intake API.

### Store

```text
workspace/
└── artifacts/
    ├── blobs/<sha256>
    └── reports/<sha256>.json
```

The store uses private directories/files where supported, atomic replacement and content-address integrity verification when a report is loaded.

## Layer 1 — Identity and mitigation observations

### ELF

- class: 32 / 64 bit;
- endianness;
- machine architecture;
- ELF type;
- bounded program-header count;
- `ET_DYN` exposed conservatively as `pie_candidate`;
- `PT_GNU_STACK` NX posture;
- `PT_GNU_RELRO` presence.

`pie_candidate` is not represented as definitive PIE. `PT_GNU_RELRO` presence is not represented as proof of Full RELRO.

### PE

- PE signature and machine architecture;
- PE32 / PE32+ bitness;
- section count;
- DLL-characteristic observations:
  - ASLR;
  - high-entropy VA;
  - NX compatibility;
  - Control Flow Guard.

### Mach-O

- thin 32 / 64-bit images;
- byte order;
- architecture;
- file type / load-command count;
- PIE flag;
- basic fat-Mach-O identity.

Fat slices are not recursively expanded yet.

## Layer 2 — Bounded section / segment inventory

Raw section contents are deliberately excluded from the structure inventory.

Hard bounds:

- maximum **256** sections in a report;
- maximum **4096** Mach-O load commands inspected.

### ELF section metadata

- index and name;
- section type;
- R/W/X posture derived from allocation/write/execute flags;
- file offset and size;
- virtual address.

### PE section metadata

- index and name;
- R/W/X characteristics;
- virtual size/address;
- raw size/file offset;
- whether the section is marked as containing code.

### Mach-O structure metadata

Segments:
- name;
- R/W/X initial protection;
- file offset/size;
- declared section count.

Sections:
- section and segment name;
- inherited segment protection;
- file offset/size;
- virtual address.

The Console renders this as a bounded section table and segment strip. The UI shows only a front window of a larger bounded report rather than trying to render unlimited rows.

## Layer 3 — Bounded linkage intelligence

No disassembly is required for this layer.

Hard bounds:

- maximum **128** libraries;
- maximum **2048** dynamic/import symbols;
- maximum **256** ELF/PE section headers scanned for linkage metadata;
- maximum **4096** Mach-O load commands.

### ELF

- `DT_NEEDED` dependencies from `SHT_DYNAMIC`;
- undefined externally relevant `SHT_DYNSYM` entries as imports;
- defined externally relevant dynamic symbols as exports.

### PE

- Import Directory RVA resolved through the bounded section map;
- imported DLL names;
- name or ordinal imports from thunk metadata.

### Mach-O

- linked dylib names from bounded dylib load commands.

Mach-O symbol-table import/export expansion and PE export parsing are later static layers.

## Static exploitability review signals

`assess_artifact()` converts already-parsed metadata into bounded **review signals**, not vulnerability verdicts.

Examples:

- an observed writable+executable section/segment;
- an explicitly absent NX/ASLR/PIE/RELRO/CFG-style metadata flag;
- linkage to APIs that merit caller/data-flow review, such as unbounded string-copy or raw-memory-copy functions.

Every signal carries:

- code/category;
- severity;
- confidence;
- evidence basis;
- a static-review recommendation;
- `vulnerability_confirmed=false`;
- `execution_authority=false`.

The assessment object also fixes:

- `mode=static-report-only`;
- `payload_generated=false`;
- `artifact_executed=false`.

A linked API by itself is never treated as proof of a vulnerability.

## Next static layers

1. PE exports and Mach-O symbol-table expansion.
2. Relocation metadata.
3. Redaction-aware bounded printable-string observations.
4. Optional typed disassembly backend with instruction/byte/function budgets.
5. Evidence-linked call-site and control-flow observations.
6. Human-reviewed exploitability synthesis that stops at a non-executed verification plan.

No step in this roadmap changes the mandatory REPORT_ONLY boundary.
