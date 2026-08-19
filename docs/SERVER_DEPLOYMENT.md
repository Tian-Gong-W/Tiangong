# TONMEN Server Deployment

TONMEN runs in **local execution mode by default** and can optionally split into a governed control plane plus remote execution workers. The web Console intentionally binds to loopback only in both designs. Do not expose port 8888 directly to the public Internet.

For the distributed execution protocol, worker secrets, routing and service examples, see `docs/WORKERS.md`.

## Recommended hardware profiles

### Development / control-only

- 2–4 vCPU
- 4–8 GiB RAM
- 40–80 GiB SSD
- Suitable for development, dry runs, light evidence review, and remote AI providers.

### Recommended single-node deployment

- 8 vCPU
- 16 GiB RAM
- 160–250 GiB NVMe/SSD
- 1 Gbps network
- Static public IPv4 when assessments need a stable allowlisted egress address

This is the default target for a TONMEN host that runs the Console, Chronicle/Reports, Nmap/httpx/Nuclei, Lead AI orchestration, and 3–5 evidence-only Council reviewers.

### Recommended split deployment

When execution traffic should come from dedicated nodes, keep governance centralized and move only typed tool execution to Workers.

**Control plane**

- 4–8 vCPU
- 8–16 GiB RAM
- 100–250 GiB NVMe/SSD
- Console / Scope / Guard / Approval / Mission / Chronicle / Reports / Lead AI / Provider Hub
- no scanner egress required when all execution is remote

**General execution worker**

- 8 vCPU
- 16 GiB RAM
- 80–160 GiB SSD/NVMe
- Nmap, httpx, Nuclei and Nuclei templates installed locally
- stable egress IP when target owners allowlist assessment traffic

Add workers for additional regions or parallel capacity instead of turning one node into an unrestricted executor. Every Worker independently rechecks its local Scope/Policy and rebuilds argv from the typed adapter; the control-plane Approval Token and raw shell commands are never sent to it.

### Heavy / multi-mission single node

- 16 vCPU
- 32 GiB RAM
- 300–500 GiB NVMe
- 1 Gbps or better network
- Dedicated execution egress IP

This remains useful for a simple all-in-one installation, but once several missions or egress regions are needed, prefer the Worker Plane.

### GPU

No GPU is required when Lead/Council models are remote providers. If local LLM inference is added later, use a separate GPU worker rather than coupling model VRAM requirements to the security execution host.

## Operating system

Use a current supported Linux LTS release. TONMEN itself requires Python 3.10 or newer and CI covers Python 3.10, 3.11, and 3.12.

A conservative production baseline is:

- Ubuntu Server 24.04 LTS
- Python 3.11 or 3.12 virtual environment
- Nmap, httpx, and Nuclei installed and verified with `tonmen doctor` on every execution node
- Nuclei templates installed and readable by the TONMEN service account on every Worker that carries the `nuclei` role/tag

## Filesystem layout

Suggested control-plane layout:

```text
/opt/tonmen/                 application checkout + virtualenv
/etc/tonmen/tonmen.toml      project configuration
/etc/tonmen/ai.env           provider / worker environment secrets (0640 or stricter)
/var/lib/tonmen/             Chronicle, Reports, Audit and runtime workspace
```

Suggested Worker layout:

```text
/opt/tonmen/                 application checkout + virtualenv
/etc/tonmen/tonmen.toml      worker-local Scope / runtime configuration
/etc/tonmen/worker.env       worker shared secret (0640 or stricter)
/var/lib/tonmen-worker/      worker-local Audit and runtime files
```

Example project configuration:

```toml
[tonmen]
workspace = "/var/lib/tonmen"
bind_host = "127.0.0.1"
bind_port = 8888
command_timeout_seconds = 120
allow_arbitrary_shell = false

[scope]
allowed_targets = ["127.0.0.1", "::1", "localhost"]
denied_targets = []
```

Only add targets that are explicitly authorized. Worker Scope should be the same as, or narrower than, the control-plane Scope.

## Provider and budget environment

Store AI credentials in a root/service-readable environment file rather than `tonmen.toml`.

Example `/etc/tonmen/ai.env`:

```bash
TONMEN_AI_PROVIDER=openai
TONMEN_AI_MODEL=gpt-5.6
TONMEN_AI_POOL=chatgpt,google,grok,deepseek,mistral

TONMEN_AI_MISSION_TOKEN_BUDGET=120000
TONMEN_AI_PROVIDER_TOKEN_BUDGETS=chatgpt=30000,google=25000,grok=25000,deepseek=30000,mistral=15000
TONMEN_AI_PROVIDER_FAILURE_LIMIT=2
TONMEN_AI_FAILOVER=1

OPENAI_API_KEY=...
DEEPSEEK_API_KEY=...
MISTRAL_API_KEY=...
```

The provider budgets above are TONMEN-local guardrails. They are not provider billing balances.

Protect the file:

```bash
sudo chown root:tonmen /etc/tonmen/ai.env
sudo chmod 0640 /etc/tonmen/ai.env
```

Browser-login providers (ChatGPT/Codex, Google, Grok) continue to delegate authentication and credential storage to their official CLIs. TONMEN does not read those credential stores.

## Optional Worker execution mode

Worker execution must be explicitly enabled on the control plane:

```bash
export TONMEN_EXECUTION_MODE=worker
export TONMEN_WORKERS='uae-1@http://10.77.0.11:8890#region=uae#tags=web,nmap,nuclei#secret_env=TONMEN_WORKER_SECRET_UAE1#weight=2'
export TONMEN_WORKER_SECRET_UAE1='same-long-random-secret-configured-on-worker'

# Only when 10.77.0.11 is reached through an encrypted private overlay:
export TONMEN_WORKER_ALLOW_INSECURE_HTTP=1
```

The preferred topology is WireGuard/Tailscale/private VPC connectivity. Worker port 8890 should not be Internet-accessible. For an Internet-routable transport, terminate TLS and restrict access so the control plane is the only caller.

## Console access

Run TONMEN on the control server with the Console still bound to `127.0.0.1`:

```bash
tonmen --config /etc/tonmen/tonmen.toml console --no-open
```

Access it from an operator workstation through an SSH tunnel:

```bash
ssh -L 8888:127.0.0.1:8888 tonmen@SERVER_IP
```

Then open `http://127.0.0.1:8888/` on the operator workstation.

For persistent team access, put the server and operator devices on a private WireGuard/Tailscale-style network and still keep the TONMEN HTTP listener on loopback. If a reverse proxy is introduced later, add explicit authenticated-session and trusted-proxy handling before relaxing the loopback invariant.

## systemd control-plane example

```ini
[Unit]
Description=TONMEN governed security orchestration control plane
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=tonmen
Group=tonmen
WorkingDirectory=/opt/tonmen
EnvironmentFile=/etc/tonmen/ai.env
ExecStart=/opt/tonmen/.venv/bin/tonmen --config /etc/tonmen/tonmen.toml console --no-open
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/tonmen

[Install]
WantedBy=multi-user.target
```

Validate tool permissions after hardening. Do not grant blanket sudo or arbitrary shell access to the TONMEN service account merely to make a scanner work. Worker service examples are in `docs/WORKERS.md`.

## Network and operational controls

- Prefer stable egress IPs so target owners can allowlist and attribute authorized assessment traffic.
- Restrict inbound control-plane firewall rules to SSH/private-network administration; port 8888 should not be Internet-accessible.
- Restrict every Worker listener so only the control plane can reach it; do not publish 8890 to the Internet.
- Keep outbound HTTPS available for configured AI providers and package/template updates where required.
- Keep Chronicle/Reports/Audit on persistent storage and back them up according to their sensitivity.
- Rotate API credentials and Worker shared secrets separately from project configuration.
- Confirm the hosting provider's acceptable-use policy allows your authorized security-assessment traffic.
- Keep assessment Scope narrow. Distributed execution does not change TONMEN's Scope → Guard → Approval → Executor boundary.

## Capacity guidance

The orchestration/control layer itself is relatively light. Resource pressure is more likely to come from scanner subprocesses, retained Evidence, template sets, concurrent mission activity and AI/CLI calls. Start with either an 8 vCPU / 16 GiB all-in-one node or a 4–8 vCPU / 8–16 GiB control plane plus 8 vCPU / 16 GiB Workers. Measure CPU, memory, disk growth, file descriptor usage and outbound bandwidth before scaling further.
