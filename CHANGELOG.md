# Changelog

## v0.4.0-alpha — 2026-08-16

First usable TONMEN Alpha baseline.

### Product usability
- Added `tonmen doctor` readiness checks.
- Added `tonmen init` and project-local `tonmen.toml`.
- Added persistent `tonmen scope show|add|remove`.
- Added exact host, IP/CIDR, and leading-wildcard scope rules.
- Updated runtime status to show Planner, Intelligence, Reasoner, and Mission Loop readiness.
- Added Getting Started documentation and an example configuration.

### Runtime baseline
- Governed Tool Registry and `shell=False` Executor.
- Nmap, HTTPx, and Nuclei typed adapters.
- Scope, Policy, single-use approvals, and persistent audit.
- Mission planning, execution, Chronicle persistence, deterministic Intelligence, Tiance Reasoning, and bounded Tianheng Mission Loop.

### Safety
- External targets remain deny-by-default.
- Loopback scope remains built in.
- Mission Loop cannot grant itself authority, expand scope, or add free-form commands.
- Validation remains explicitly human-approved.
