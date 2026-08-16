# TONMEN v0.4.0 Alpha — Getting Started

> 人予其意，宮成其事。  
> 宮察其象，鑑明其實；天策既定，萬器乃行。

TONMEN is a governed security-agent runtime. Use it only on systems you own or are explicitly authorized to assess.

## 1. Requirements

- Python 3.10 or newer
- `nmap`
- ProjectDiscovery `httpx` CLI
- ProjectDiscovery `nuclei` CLI

`httpx` here means the ProjectDiscovery command-line scanner, **not** the Python package with the same name.

## 2. Install from source

```bash
git clone https://github.com/Top-Men-AI/TONMEN.git
cd TONMEN

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## 3. Check readiness

```bash
tonmen doctor
```

Doctor checks Python, the writable workspace, and whether Nmap / HTTPx / Nuclei are present in `PATH`.

## 4. Create a project configuration

```bash
tonmen init
tonmen scope show
```

The default scope remains loopback-only:

- `127.0.0.1`
- `::1`
- `localhost`

## 5. Add an authorized target

Exact host:

```bash
tonmen scope add app.example.test
```

CIDR:

```bash
tonmen scope add 10.20.30.0/24
```

Leading wildcard:

```bash
tonmen scope add '*.example.test'
```

Only add assets for which you have explicit authorization.

Remove a custom rule:

```bash
tonmen scope remove app.example.test
```

The built-in loopback rules cannot be removed.

## 6. Dry-run before execution

```bash
tonmen plan app.example.test
```

Planning does not execute tools.

## 7. Run the bounded mission loop

```bash
tonmen loop app.example.test
```

The current built-in mission uses governed Nmap → HTTPx → Nuclei capabilities. Discovery can proceed inside scope. Validation stops at the approval boundary when evidence justifies it.

Inspect state:

```bash
tonmen missions
tonmen show <run-id>
tonmen reason <run-id>
```

Cross a validation boundary only with an explicit human act:

```bash
tonmen resume <run-id> --approve
```

Approval grants are single-use, bound to the waiting tool and target, and are not persisted.

## 8. Use another config file

```bash
tonmen --config /path/to/tonmen.toml doctor
tonmen --config /path/to/tonmen.toml loop app.example.test
```

## Safety invariants

- No arbitrary shell API.
- Executor uses structured argv with `shell=False`.
- Scope is deny-by-default outside configured targets.
- Validation/intrusive actions require an explicit bound grant.
- The Mission Loop cannot self-approve or expand scope.
- Intelligence facts must point to raw evidence.
- Loop budgets and stop reasons are persisted in Chronicle.
