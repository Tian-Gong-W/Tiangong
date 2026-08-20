# TONMEN Worker Queue and Concurrency Scheduler

The Worker scheduler limits **where and how many** governed tool executions may run concurrently. It does not grant execution authority: every job still follows control-plane Scope / Guard / Approval and the Worker repeats its own local Scope / Policy / adapter validation.

## Two concurrency limits

Configure the same or a lower capacity on the control plane than the Worker service.

Control-plane descriptor:

```bash
export TONMEN_WORKERS='uae-1@http://10.77.0.11:8890#region=uae#tags=web,nmap,nuclei#secret_env=TONMEN_WORKER_SECRET_UAE1#weight=2#concurrency=4'
```

Worker service:

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

`concurrency=4` is the scheduler's local slot count. `--max-concurrency 4` is the Worker server's hard backstop. The Worker rejects a race above its hard limit before adapter execution.

Do not set high concurrency merely because a host has many CPU cores. Nmap/Nuclei traffic and target-side rate limits often matter more than local CPU. Start at 2–4 concurrent jobs per general Worker and measure.

## Queue controls

```bash
export TONMEN_WORKER_QUEUE_TIMEOUT_SECONDS=30
export TONMEN_WORKER_MAX_QUEUE=128
```

When all eligible Workers are at capacity, a request waits in the bounded control-plane queue. It retains its original Worker id/region/tag restrictions. If no slot becomes available before the timeout, the job fails rather than bypassing placement constraints or running locally.

The scheduler is fair for jobs competing for the same Worker, but a queued job restricted to one saturated region does not block a later job that can use a different free Worker.

## Placement

Selection considers:

1. configured Worker id/region/tag constraints;
2. Secret readiness;
3. control-plane drain state;
4. available concurrency slots;
5. inflight utilization;
6. configured weight and historical success/failure pressure;
7. pre-dispatch remote health, tool readiness and reported remote capacity.

A saturated Worker can be bypassed **before dispatch** when another eligible Worker has capacity. Once the execute POST begins, TONMEN still does not run the same ambiguous job on another Worker automatically.

## Drain / maintenance

The `/workers` Fleet workspace includes `Drain / 维护` and `恢复派发` actions.

Drain means:

- stop granting new scheduler leases to that Worker;
- allow current inflight jobs to finish normally;
- keep Scope / Guard / Approval behavior unchanged;
- keep the Worker process online for health inspection;
- do not kill scanner subprocesses.

Drain is currently control-plane runtime state. Restarting the control plane clears it, so use service/network maintenance controls as well for long maintenance windows.

## Capacity health

Worker `/v1/health` reports only safe capacity metadata:

```json
{
  "capacity": {
    "inflight": 2,
    "max_concurrency": 4,
    "available_slots": 2,
    "accepting_jobs": true
  }
}
```

The Fleet Console sanitizes cached health responses before browser exposure. Unknown remote fields are not forwarded.

## Suggested starting values

For an 8 vCPU / 16 GiB Nmap/httpx/Nuclei Worker:

```text
control-plane concurrency = 3 or 4
worker --max-concurrency  = 4
queue timeout             = 30 seconds
max queue                 = 128
```

For lightweight discovery-only Workers, higher concurrency may be reasonable after measuring. For validation-heavy Workers, prefer conservative concurrency and tool-level rate limits over a large queue of simultaneous requests.

## Multi-region example

```bash
export TONMEN_EXECUTION_MODE=worker
export TONMEN_WORKER_MAX_QUEUE=128
export TONMEN_WORKER_QUEUE_TIMEOUT_SECONDS=45

export TONMEN_WORKERS='uae-1@http://10.77.0.11:8890#region=uae#tags=web,nmap,nuclei#secret_env=TONMEN_WORKER_SECRET_UAE1#weight=2#concurrency=4;eu-1@http://10.77.0.12:8890#region=eu#tags=web,nmap,nuclei#secret_env=TONMEN_WORKER_SECRET_EU1#weight=1#concurrency=3'
```

Use the private encrypted overlay guidance in `WORKERS.md`; do not expose Worker port 8890 directly to the public Internet.
