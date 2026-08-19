# TONMEN Worker Plane

TONMEN can run as a **control plane + one or more execution workers**. Worker mode changes only where typed tool adapters execute. It does not move Scope, Guard, Approval, Mission, Chronicle, Reasoner, Lead AI, or Council authority away from the control plane.

```text
Operator
   |
   | SSH / private access
   v
+-------------------------------------+
| TONMEN Control Plane                |
| Console 127.0.0.1:8888              |
| Scope -> Guard -> Approval           |
| Mission / Chronicle / Reports       |
| Lead AI / Provider Hub              |
+-------------------+-----------------+
                    |
                    | signed typed job envelope
                    | no Approval Token / no raw shell
                    v
        +-----------+-----------+
        |                       |
+-------+--------+      +-------+--------+
| Worker uae-1  |      | Worker eu-1   |
| local Scope   |      | local Scope    |
| local Guard   |      | local Guard    |
| Tool adapters |      | Tool adapters  |
| shell=False   |      | shell=False    |
+-------+--------+      +-------+--------+
        |                       |
        v                       v
  Authorized targets       Authorized targets
```

## Security model

Every remote execution is gated twice:

1. The control plane validates the typed adapter request.
2. Control-plane Scope and Policy are evaluated.
3. If required, a single-use Approval Grant is consumed on the control plane.
4. The control plane creates a worker-bound HMAC-SHA256 envelope containing only the tool name, typed parameters, target, safe mission context and an approval-granted boolean.
5. The envelope has a nonce and short TTL (default 60 seconds, maximum 300 seconds).
6. The worker verifies the signature, worker id, TTL and replay state.
7. The worker independently evaluates its own Scope and Policy.
8. The worker checks its local tool readiness and rebuilds argv from the local adapter.
9. The worker executes with `shell=False`.
10. Evidence is returned with worker id/region/tags/remote job provenance.

The control-plane Approval Token is **never sent to the worker**. A validation-risk worker uses the signed `approval_granted` claim only to mint a one-request local approval after its own policy has independently reached `require_approval`.

Workers never receive a raw shell command or control-plane argv. They receive the same structured adapter parameters used by local execution and rebuild argv locally.

## Worker secret

Use a separate random secret per worker. Use at least 32 bytes. Keep it in an environment file or secret manager; do not put the value in `tonmen.toml`, Chronicle, Reports, browser state, or `TONMEN_WORKERS`.

Example on `uae-1`:

```bash
export TONMEN_WORKER_SECRET_UAE1='replace-with-a-long-random-secret'
```

Start the worker using the environment variable name, not the secret itself:

```bash
tonmen --config /etc/tonmen/tonmen.toml worker \
  --id uae-1 \
  --host 10.77.0.11 \
  --port 8890 \
  --region uae \
  --tags web,nmap,nuclei \
  --secret-env TONMEN_WORKER_SECRET_UAE1 \
  --allow-remote-bind
```

A worker defaults to `127.0.0.1`. A non-loopback bind requires `--allow-remote-bind`. Wildcard binds (`0.0.0.0` and `::`) remain rejected.

## Network placement

Do **not** expose worker port 8890 to the public Internet.

Recommended choices:

- WireGuard private network between control plane and workers
- Tailscale/Headscale private overlay
- private VPC/subnet with firewall rules allowing only the control-plane address
- HTTPS reverse proxy with authenticated private routing

The built-in worker server is HTTP. For a remote `http://` worker, the control plane refuses the connection unless you explicitly set:

```bash
export TONMEN_WORKER_ALLOW_INSECURE_HTTP=1
```

Use that only when the underlying transport is already encrypted and private (for example WireGuard/Tailscale). Otherwise use an HTTPS endpoint.

## Configure the control plane

Worker mode is explicit. Merely defining workers does not move execution away from the local host.

```bash
export TONMEN_EXECUTION_MODE=worker

export TONMEN_WORKERS='uae-1@http://10.77.0.11:8890#region=uae#tags=web,nmap,nuclei#secret_env=TONMEN_WORKER_SECRET_UAE1#weight=2;eu-1@http://10.77.0.12:8890#region=eu#tags=web,nmap,nuclei#secret_env=TONMEN_WORKER_SECRET_EU1#weight=1'

export TONMEN_WORKER_SECRET_UAE1='same-secret-as-uae-worker'
export TONMEN_WORKER_SECRET_EU1='same-secret-as-eu-worker'

# Only when the addresses above are inside an encrypted private overlay:
export TONMEN_WORKER_ALLOW_INSECURE_HTTP=1
```

`TONMEN_WORKERS` contains descriptors only. The `secret_env=` option names the environment variable that holds that worker's secret.

Descriptor format:

```text
id@url#region=<region>#tags=<comma,list>#secret_env=<ENV_NAME>#weight=<positive-number>
```

## Routing

The default strategy is health-gated weighted least-use. Before dispatch, the control plane probes candidate workers and only selects a worker that reports the requested adapter ready.

Global routing constraints can be set with:

```bash
export TONMEN_WORKER_REGION=uae
export TONMEN_WORKER_TAGS=web,nuclei
```

A trusted mission context may also carry `worker_id`, `worker_region`, or `worker_tags`; those fields only restrict placement and cannot expand Scope or tool semantics.

Worker weights affect load preference. A worker with `weight=2` can absorb roughly more work before its least-use score catches up with a worker at `weight=1`.

## Failure behavior

TONMEN is deliberately conservative around remote execution ambiguity.

- If a worker health probe fails **before dispatch**, another eligible worker may be selected.
- If the selected worker says the requested tool is not ready, another eligible worker may be selected.
- Once the execute POST has begun, TONMEN does **not** automatically run the same job on a second worker when the response is lost or times out. The first worker may already have executed the action.
- An exact retry to the same worker uses the same signed job identity and is idempotent when the worker already has a completed result cached.

This avoids duplicating validation traffic just because the control plane lost a response.

## Scope on workers

Each worker uses its own `tonmen.toml`. Its Scope should be the same as, or narrower than, the control plane's Scope.

Example worker configuration:

```toml
[tonmen]
workspace = "/var/lib/tonmen-worker"
bind_host = "127.0.0.1"
bind_port = 8888
command_timeout_seconds = 120
allow_arbitrary_shell = false

[scope]
allowed_targets = ["127.0.0.1", "::1", "localhost", "authorized.example.com"]
denied_targets = []
```

A control-plane authorization cannot override a worker-local deny rule.

## Suggested hardware

### Control plane

For a control plane that no longer runs scanners locally:

- 4–8 vCPU
- 8–16 GiB RAM
- 100–250 GiB NVMe/SSD for Chronicle, Reports and Audit
- no GPU required for remote AI providers

### General worker

- 4 vCPU / 8 GiB RAM for light Nmap/httpx work
- **8 vCPU / 16 GiB RAM** for a balanced Nmap/httpx/Nuclei worker
- 80–160 GiB SSD/NVMe for binaries, Nuclei templates, temporary output and local audit
- stable egress IP if the target owner allowlists source addresses

For parallel missions, prefer adding more governed workers instead of giving one worker unlimited concurrency. Worker concurrency limits/queues are a later control-plane feature; the first worker protocol is intentionally synchronous and fail-closed.

## systemd worker example

```ini
[Unit]
Description=TONMEN governed execution worker uae-1
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=tonmen
Group=tonmen
WorkingDirectory=/opt/tonmen
EnvironmentFile=/etc/tonmen/worker.env
ExecStart=/opt/tonmen/.venv/bin/tonmen --config /etc/tonmen/tonmen.toml worker --id uae-1 --host 10.77.0.11 --port 8890 --region uae --tags web,nmap,nuclei --secret-env TONMEN_WORKER_SECRET_UAE1 --allow-remote-bind
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/tonmen-worker

[Install]
WantedBy=multi-user.target
```

Firewall the worker so only the control plane can reach port 8890. Do not grant the worker service account blanket sudo or arbitrary shell access.
