# TONMEN Security Model

TONMEN is designed for authorized security assessment and defensive research.

## Default posture

- External targets are denied by default. The built-in default scope contains only localhost.
- Arbitrary shell execution is disabled by design.
- Tool adapters accept typed, bounded parameters and produce argv for `shell=False` execution.
- Validation and intrusive actions require a short-lived, single-use approval grant.
- Approval grants are bound to one tool and one exact target.
- Destructive capabilities are denied by policy.
- MCP cannot issue approval grants for itself.
- Execution decisions are written to an append-only JSONL audit log.

## Scope

Operators must explicitly configure targets they are authorized to assess. Deny rules override allow rules.

Supported scope forms include exact hostnames/IPs, wildcard subdomains such as `*.lab.example.com`, and IP CIDRs such as `10.20.0.0/16`.

## Reporting vulnerabilities in TONMEN

Please open a private security advisory in this repository rather than publishing exploit details in a public issue.
