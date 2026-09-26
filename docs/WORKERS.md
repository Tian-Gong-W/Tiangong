# TONMEN Worker Plane

TONMEN supports a governed **control plane + one or more execution Workers**. Worker mode changes where typed adapters execute; it does not move Scope, Guard, Approval, Mission, Chronicle, Reasoner, Lead AI, or Council authority away from the control plane.

```text
Operator
   |
   v
+-------------------------------------+
| TONMEN Control Plane                |
| Scope -> Guard -> Approval           |
| Mission / Chronicle / Reports       |
| Lead AI / Provider Hub              |
| Worker Queue / Scheduler            |
+-------------------+-----------------+
                    |
                    | HMAC signed typed job
                    | no Approval Token / raw shell / raw argv
          +---------+---------+
          v                   v
+------------------+   +------------------+
| Worker uae-1     |   | Worker eu-1      |
| local Scope      |   | local Scope       |
| local Policy     |   | local Policy      |
| hard concurrency |   | hard concurrency |
| adapters         |   | adapters         |
| shell=False      |   | shell=False      |
+------------------+   +------------------+
```

## Security model

Every remote execution is gated twice. The control plane validates the typed request, checks Scope/Policy and consumes any required single-use Approval Grant. It then signs a short-lived, worker-bound envelope containing only tool name, typed parameters, target, safe mission context and an approval-granted boolean.

The Worker verifies HMAC, Worker id, TTL and replay state, independently evaluates its own Scope/Policy, checks local readiness, rebuilds argv from the local adapter and executes with `shell=False`.

The control-plane Approval Token is **never sent** to the Worker. Workers never receive arbitrary shell strings or control-plane argv. Worker evidence is returned with Worker id/region/tags/remote-job provenance.

## Secrets

Use a separate random secret of at least 32 bytes per Worker and keep it in an environment file or secret manager.

```bash
export TONMEN_WORKER_SECRET_UAE1='replace-with-a-long-random-secret'
```

Do not put the secret value in `TONMEN_WORKERS`, `tonmen.toml`, Chronicle, Reports, or browser state. `secret_env=` contains only the environment-variable name.

## Start a Worker

```bash
tonmen --config /etc/tonmen/tonmen.toml worker \
  --id uae-1 \
  --host 10.77.0.11 \
  --port 8890 \
  --region uae \
  --tags web,nmap,nuclei \
  --max-concurrency 4 \
  --secret-env TONMEN_WORKER_SECRET_UAE1 \
  --allow-remote-bind
```

A Worker defaults to loopback. A non-loopback bind requires `--allow-remote-bind`; wildcard `0.0.0.0` and `::` remain rejected.

## Network placement

Do **not** expose port 8890 directly to the public Internet. Prefer WireGuard, Tailscale/Headscale, a private VPC/subnet, or a private HTTPS route. Remote plain HTTP is refused unless `TONMEN_WORKER_ALLOW_INSECURE_HTTP=1` is explicitly set; use that only when the underlying network is already encrypted and private.

## Configure the control plane

Worker execution is opt-in:

```bash
export TONMEN_EXECUTION_MODE=worker
export TONMEN_WORKER_ALLOW_INSECURE_HTTP=1
export TONMEN_WORKER_MAX_QUEUE=128
export TONMEN_WORKER_QUEUE_TIMEOUT_SECONDS=30

export TONMEN_WORKERS='uae-1@http://10.77.0.11:8890#region=uae#tags=web,nmap,nuclei#secret_env=TONMEN_WORKER_SECRET_UAE1#weight=2#concurrency=4;eu-1@http://10.77.0.12:8890#region=eu#tags=web,nmap,nuclei#secret_env=TONMEN_WORKER_SECRET_EU1#weight=1#concurrency=3'
```

Descriptor format:

```text
id@url#region=<region>#tags=<comma,list>#secret_env=<ENV_NAME>#weight=<positive-number>#concurrency=<1-64>
```

`concurrency=` is the control-plane slot limit. `--max-concurrency` is the Worker service hard limit. Configure the scheduler limit at or below the Worker limit.

## Routing and queueing

The scheduler is **bounded weighted least-load with a fair queue**. It considers Worker id/region/tag constraints, drain state, free slots, current utilization, configured weight, historical failures, and pre-dispatch health/tool readiness.

Optional global placement restrictions:

```bash
export TONMEN_WORKER_REGION=uae
export TONMEN_WORKER_TAGS=web,nuclei
```

When all eligible slots are busy, the request waits in the bounded queue. If it exceeds `TONMEN_WORKER_QUEUE_TIMEOUT_SECONDS`, it fails instead of bypassing placement or falling back to local execution.

See `WORKER_SCHEDULER.md` for scheduler details.

## Drain / maintenance

The `/workers` Fleet workspace can mark a Worker `DRAINING`. Drain blocks **new** leases but does not kill inflight jobs. Activate the Worker again when maintenance is complete.

Drain is currently control-plane runtime state and resets when the control plane restarts.

## Failure behavior

TONMEN remains conservative around ambiguous remote execution:

- health/tool/capacity failure **before POST** may select another eligible Worker;
- Worker hard-capacity races are rejected before tool execution;
- after POST begins, a lost/timeout response does **not** trigger automatic execution on another Worker;
- exact retry to the same Worker remains idempotent when a completed result is cached.

## Worker Scope

Each Worker has its own `tonmen.toml`. Worker Scope should be equal to or narrower than control-plane Scope. A control-plane authorization cannot override a Worker-local deny rule.

## Suggested hardware and concurrency

A useful baseline:

```text
Control plane   4–8 vCPU / 8–16 GiB / persistent NVMe
General Worker  8 vCPU / 16 GiB / 80–160 GiB SSD/NVMe
GPU             not required for remote AI providers
```

For an 8 vCPU / 16 GiB general Nmap/httpx/Nuclei Worker, start around **3–4 concurrent jobs**, not dozens. Tool rate limits and target-side load are often more important than host CPU. Scale by adding governed Workers rather than removing concurrency limits.

## systemd example

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
ExecStart=/opt/tonmen/.venv/bin/tonmen --config /etc/tonmen/tonmen.toml worker --id uae-1 --host 10.77.0.11 --port 8890 --region uae --tags web,nmap,nuclei --max-concurrency 4 --secret-env TONMEN_WORKER_SECRET_UAE1 --allow-remote-bind
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

Firewall the Worker so only the control plane/private overlay can reach it. Do not grant blanket sudo or arbitrary shell access merely to make a scanner work.
