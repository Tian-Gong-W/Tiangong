# Resolved Asset Set and Scope-aware Coverage

TONMEN treats DNS resolution as an asset observation, never as an authorization grant.

## States

A hostname mission may record multiple A/AAAA answers. Each concrete address is classified against the mission Scope snapshot:

- `authorized` — the IP is independently covered by an allowed IP/CIDR rule and is not denied.
- `needs_scope` — the address was observed but is not independently authorized for direct execution.

Authorizing `example.com` does not automatically authorize every IP returned by DNS as a direct target.

## Direct resolved-IP coverage

Direct Nmap fan-out is deliberately opt-in so upgrades do not silently increase network traffic:

```bash
export TONMEN_RESOLVED_IP_COVERAGE=1
```

Even with the switch enabled, TONMEN adds an extra Nmap step only for addresses whose concrete IP is already allowed by Scope. A `needs_scope` address never becomes an execution step.

Example:

```toml
[scope]
allowed_targets = ["example.com", "203.0.113.0/24"]
```

If DNS returns `203.0.113.10` and `198.51.100.20`, only `203.0.113.10` is eligible for direct coverage. Add a concrete IP/CIDR to Scope and create a new Mission plan before covering the other address.

## Web coverage

HTTPx and Nuclei continue to use the hostname rather than directly fan out to resolved IPs. This preserves Host headers, TLS SNI and application/CDN routing semantics. Direct per-backend web validation requires a future typed backend-routing capability rather than replacing the hostname with a raw IP.

## Provenance

Mission Graph records:

- `asset.resolved` nodes for A/AAAA observations and Scope classification.
- `coverage.plan` for eligible/planned direct Nmap targets and the hostname-preserving web rule.

Chronicle persists the Plan metadata and Graph. Final reports expose `asset_coverage` and keep Nmap-observed `resolved_not_scanned` addresses distinct from scanned addresses.

## Time semantics

TONMEN canonical structured timestamps are UTC. Raw Evidence is kept verbatim and can contain tool-specific timezone text such as HKT. Reports label the canonical timezone explicitly instead of rewriting raw tool output.
