import {
  AssetDomain,
  ChainEdge,
  ChainNode,
  ControlPlaneSnapshot,
  EvidenceItem,
  ExecutionEvent,
  Finding,
  MissionDetail,
  Task,
  TaskStatus,
  WorkerNode,
} from './types';

const TOKEN_KEY = 'tonmen.web.token';

export const savedToken = () => sessionStorage.getItem(TOKEN_KEY) || '';
export const forgetToken = () => sessionStorage.removeItem(TOKEN_KEY);
export const rememberToken = (token: string) => sessionStorage.setItem(TOKEN_KEY, token);

async function request<T>(path: string, init: RequestInit = {}, token = savedToken()): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body) headers.set('Content-Type', 'application/json');
  const response = await fetch(path, { ...init, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload?.error || payload?.technical || `HTTP ${response.status}`;
    const error = new Error(String(message));
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }
  return payload as T;
}

export async function authenticate(token: string): Promise<void> {
  await request('/api/auth/status', {}, token.trim());
  rememberToken(token.trim());
}

const post = <T>(path: string, body: Record<string, unknown> = {}) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) });

const asRecord = (value: unknown): Record<string, any> =>
  value && typeof value === 'object' ? (value as Record<string, any>) : {};

const dateText = (value: unknown) => {
  if (!value) return '—';
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN');
};

const phaseFor = (tool: string): ExecutionEvent['phase'] => {
  if (tool === 'nmap') return 'recon';
  if (tool === 'httpx') return 'fingerprint';
  if (tool === 'nuclei') return 'vuln_verify';
  return 'ai_reasoning';
};

const eventStatus = (state: string): ExecutionEvent['status'] => {
  if (['succeeded', 'degraded'].includes(state)) return 'completed';
  if (['failed', 'denied'].includes(state)) return 'failed';
  if (state === 'running') return 'running';
  return 'pending';
};

const taskStatus = (state: string): TaskStatus => {
  if (state === 'waiting_approval') return 'waiting_approval';
  if (state === 'succeeded') return 'completed';
  if (['failed', 'denied'].includes(state)) return 'failed';
  return 'running';
};

const chainType = (kind: string): ChainNode['type'] => {
  if (kind === 'goal') return 'target';
  if (kind === 'intent') return 'probe';
  if (kind === 'fact') return 'tech';
  if (kind === 'finding') return 'vulnerability';
  return 'reasoning';
};

const chainStatus = (item: Record<string, any>): ChainNode['status'] => {
  const kind = String(item.kind || '');
  const state = String(item.state || '');
  if (kind === 'finding') {
    const evidenceStatus = String(item.evidence_status || '');
    if (evidenceStatus === 'confirmed') return 'confirmed';
    if (['failed', 'rejected', 'denied'].includes(evidenceStatus)) return 'alert';
    return 'pending';
  }
  if (['succeeded', 'degraded', 'confirmed'].includes(state)) return 'confirmed';
  if (['running', 'active'].includes(state)) return 'active';
  if (['failed', 'denied', 'blocked'].includes(state)) return 'alert';
  return 'pending';
};

function rawFindings(detail: Record<string, any>): any[] {
  const report = asRecord(detail.report);
  if (Array.isArray(report.aggregated_findings)) return report.aggregated_findings;
  const workspaceFindings = asRecord(detail.workspace).findings;
  return Array.isArray(workspaceFindings) ? workspaceFindings : [];
}

function findingId(item: any, index: number): string {
  return String(item.id || item.template_id || `finding-${index}`);
}

function mapChain(detail: Record<string, any>): { nodes: ChainNode[]; edges: ChainEdge[] } {
  const exploration = asRecord(asRecord(detail.workspace).exploration);
  const rawNodes = Array.isArray(exploration.nodes) ? exploration.nodes : [];
  const rawEdges = Array.isArray(exploration.edges) ? exploration.edges : [];
  return {
    nodes: rawNodes.map((item: any) => ({
      id: String(item.id),
      label: String(item.title || item.label || item.id),
      subLabel: String(item.tool || item.kind || ''),
      type: chainType(String(item.kind || '')),
      status: chainStatus(item),
      details: String(item.detail || ''),
      evidenceId: item.evidence_id ? String(item.evidence_id) : undefined,
      severity: item.severity
        ? (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'].includes(String(item.severity).toUpperCase())
            ? String(item.severity).toUpperCase()
            : 'INFO') as ChainNode['severity']
        : undefined,
    })),
    edges: rawEdges.map((item: any) => ({
      from: String(item.source),
      to: String(item.target),
      label: String(item.relation || ''),
      animated: false,
    })),
  };
}

function mapAssets(detail: Record<string, any>): AssetDomain {
  const workspaceAssets = asRecord(asRecord(detail.workspace).assets);
  const nodes = Array.isArray(workspaceAssets.nodes) ? workspaceAssets.nodes : [];
  const edges = Array.isArray(workspaceAssets.edges) ? workspaceAssets.edges : [];
  const hostNodes = nodes.filter((item: any) => ['ip', 'backend'].includes(String(item.kind)));
  const services = nodes.filter((item: any) => item.kind === 'service');
  const findings = nodes.filter((item: any) => item.kind === 'finding');
  return {
    id: String(workspaceAssets.root_id || `asset:${detail.id || detail.target}`),
    domain: String(detail.target || ''),
    scopeStatus: 'in_scope',
    totalHosts: hostNodes.length,
    checkedHosts: hostNodes.filter((item: any) => item.coverage_status === 'scanned').length,
    hosts: hostNodes.map((host: any) => {
      const hostServices = services.filter((service: any) =>
        edges.some((edge: any) => edge.source === host.id && edge.target === service.id),
      );
      const relatedFindings = findings.filter((finding: any) =>
        edges.some((edge: any) => edge.source === host.id && edge.target === finding.id),
      );
      const scanned = host.coverage_status === 'scanned';
      return {
        ip: String(host.title || host.id),
        status: relatedFindings.length ? 'has_vuln' : scanned ? 'checked' : 'unchecked',
        services: hostServices.map((service: any) => ({
          port: Number(service.port || 0),
          protocol: String(service.protocol || ''),
          service: String(service.service || service.title || ''),
          status: scanned ? 'checked' : 'unchecked',
          findingIds: relatedFindings.map((finding: any) => String(finding.id).replace(/^asset:finding:/, '')),
        })),
      };
    }),
  };
}

function mapEvents(detail: Record<string, any>): ExecutionEvent[] {
  const steps = Array.isArray(detail.steps) ? detail.steps : [];
  const evidence = Array.isArray(detail.evidence) ? detail.evidence : [];
  const findings = rawFindings(detail);
  return steps.map((step: any, index: number) => {
    const proof = evidence.find((item: any) => item.id === step.evidence_id);
    const start = proof?.started_at || detail.started_at;
    const finish = proof?.finished_at;
    const elapsed = start && finish ? Math.max(0, new Date(finish).getTime() - new Date(start).getTime()) : 0;
    const raw = [proof?.stdout, proof?.stderr].filter(Boolean).join('\n');
    const relatedFindingIds = step.evidence_id
      ? findings
          .map((item: any, findingIndex: number) => ({ item, id: findingId(item, findingIndex) }))
          .filter(({ item }: any) => Array.isArray(item.evidence_ids) && item.evidence_ids.includes(step.evidence_id))
          .map(({ id }: any) => id)
      : [];
    return {
      id: String(step.id || `step-${index}`),
      timestamp: String(start || ''),
      timeDisplay: dateText(start),
      title: String(step.rationale || step.tool || `步骤 ${index + 1}`),
      phase: phaseFor(String(step.tool || '')),
      status: eventStatus(String(step.state || 'pending')),
      tool: String(step.tool || '—'),
      target: String(step.target || detail.target || ''),
      duration: finish ? `${Math.round(elapsed / 1000)}s` : '—',
      workerNode: String(step.metadata?.worker_id || 'local'),
      outputSummary: String(step.error || (proof ? `exit ${proof.exit_code}` : '尚无执行证据')),
      rawOutput: raw,
      evidenceId: step.evidence_id ? String(step.evidence_id) : undefined,
      findingId: relatedFindingIds[0],
      findingIds: relatedFindingIds.length ? relatedFindingIds : undefined,
      traceType: relatedFindingIds.length ? 'initial_discovery' : String(step.tool || '') === 'nmap' ? 'recon' : undefined,
      workerTrace: proof
        ? {
            workerId: String(step.metadata?.worker_id || 'local'),
            command: Array.isArray(proof.argv) ? proof.argv.join(' ') : '',
            exitCode: Number(proof.exit_code ?? 0),
            executionTimeMs: elapsed,
          }
        : undefined,
    };
  });
}

function mapFindings(detail: Record<string, any>, taskName: string): Finding[] {
  const raw = rawFindings(detail);
  const evidence = Array.isArray(detail.evidence) ? detail.evidence : [];
  return raw.map((item: any, index: number) => {
    const itemEvidence = evidence.filter((proof: any) => (item.evidence_ids || []).includes(proof.id));
    const evidenceStatus = String(item.evidence_status || 'unverified');
    const verified = evidenceStatus === 'confirmed';
    const severity = String(item.severity || 'INFO').toUpperCase() as Finding['severity'];
    const firstPayload = Array.isArray(item.instances) ? item.instances[0] : null;
    const backends = Array.isArray(item.affected_backends)
      ? item.affected_backends.map((entry: any) => entry.backend).filter(Boolean)
      : [];
    const evidenceList: EvidenceItem[] = itemEvidence.map((proof: any) => ({
      id: String(proof.id),
      type: 'response',
      title: `${proof.tool} · exit ${proof.exit_code}`,
      timestamp: dateText(proof.finished_at),
      target: String(proof.target || detail.target || ''),
      content: [proof.stdout, proof.stderr].filter(Boolean).join('\n'),
      metadata: { command: Array.isArray(proof.argv) ? proof.argv.join(' ') : '' },
      isVerified: verified,
    }));
    return {
      id: findingId(item, index),
      taskId: String(detail.id),
      taskName,
      title: String(item.name || item.template_id || '未命名发现'),
      severity: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'].includes(severity) ? severity : 'INFO',
      status: verified ? 'confirmed' : ['pending', 'verifying'].includes(evidenceStatus) ? 'verifying' : 'candidate',
      affectedAsset: String(backends.join(', ') || detail.target || ''),
      affectedUrl: String(firstPayload?.matched_at || firstPayload?.url || detail.target || ''),
      cve: item.classification?.['cve-id']?.[0] || undefined,
      cvss: Number(item.classification?.['cvss-score'] || 0) || undefined,
      discoveryTime: dateText(firstPayload?.timestamp || detail.finished_at || detail.started_at),
      summary: String(item.description || ''),
      impact: String(item.impact || ''),
      verification: {
        verified,
        verifiedAt: verified ? dateText(firstPayload?.timestamp || detail.finished_at) : '—',
        method: evidenceStatus,
        reproducibilityRate: undefined,
        antiHallucinationCheck: String(item.attribution_status || 'unverified'),
        verifierWorker: String(item.verifier_worker || '—'),
      },
      evidenceList,
      pocCommand: Array.isArray(itemEvidence[0]?.argv) ? itemEvidence[0].argv.join(' ') : '',
      remediation: String(item.remediation || ''),
      aiJudgment: '',
    };
  });
}

export function missionToTask(mission: MissionDetail): { task: Task; findings: Finding[] } {
  const detail = asRecord(mission);
  const report = asRecord(detail.report);
  const steps = Array.isArray(detail.steps) ? detail.steps : [];
  const completed = steps.filter((step: any) => ['succeeded', 'degraded', 'failed', 'denied', 'skipped'].includes(step.state)).length;
  const active = steps.find((step: any) => ['running', 'waiting_approval'].includes(step.state)) ||
    steps.find((step: any) => step.state === 'pending') || steps.at(-1);
  const name = `Mission · ${detail.target || String(detail.id).slice(0, 8)}`;
  const chain = mapChain(detail);
  const assetTree = mapAssets(detail);
  const findings = mapFindings(detail, name);
  const counts = { critical: 0, high: 0, medium: 0, low: 0 };
  findings.forEach((finding) => {
    const key = finding.severity.toLowerCase() as keyof typeof counts;
    if (key in counts) counts[key] += 1;
  });
  const waiting = steps.find((step: any) => step.state === 'waiting_approval');
  const approvalJob = asRecord(detail.approval_job);
  const approvalRunning = ['accepted', 'running'].includes(String(approvalJob.status || ''));
  const approvalTool = String(approvalJob.tool || waiting?.tool || active?.tool || '验证');
  const start = detail.started_at ? new Date(detail.started_at) : null;
  const finish = detail.finished_at ? new Date(detail.finished_at) : new Date();
  const runtimeMinutes = start && !Number.isNaN(start.getTime()) ? Math.max(0, Math.round((finish.getTime() - start.getTime()) / 60000)) : 0;
  const status = approvalRunning ? 'running' : taskStatus(String(detail.state || 'running'));
  const task: Task = {
    id: String(detail.id),
    code: `#${String(detail.id).slice(0, 8)}`,
    name,
    target: String(detail.target || ''),
    type: 'VulnAssess',
    status,
    progress: status === 'completed' || status === 'failed' ? 100 : steps.length ? Math.round((completed / steps.length) * 100) : 0,
    totalSteps: steps.length,
    completedSteps: completed,
    assignedNode: String(steps.find((step: any) => step.metadata?.worker_id)?.metadata?.worker_id || 'local'),
    runtimeMinutes,
    startTime: dateText(detail.started_at),
    currentStage: approvalRunning ? approvalTool : String(active?.tool || (steps.length ? '已结束' : '尚无步骤')),
    currentAction: approvalRunning
      ? `${approvalTool} 已批准，正在后台执行；当前验证完成前无需重复点击。`
      : String(active?.rationale || active?.error || (steps.length ? active?.state : '尚无执行记录')),
    nextAction: String(steps.find((step: any) => step.state === 'pending')?.rationale || ''),
    actionRequired: Boolean(waiting) && !approvalRunning,
    pendingApproval: waiting && !approvalRunning
      ? {
          id: String(detail.id),
          taskId: String(detail.id),
          taskName: name,
          title: `${waiting.tool} 需要批准`,
          description: String(waiting.rationale || '此步骤需要一次性人工授权。'),
          target: String(waiting.target || detail.target || ''),
          requestedAction: String(waiting.tool || ''),
          requestedScope: String(waiting.target || detail.target || ''),
          riskLevel: Number(waiting.risk || 0) >= 4 ? 'CRITICAL' : Number(waiting.risk || 0) >= 3 ? 'HIGH' : 'MEDIUM',
          timestamp: dateText(detail.started_at),
          proposedCommand: String(waiting.tool || ''),
          reason: String(waiting.rationale || ''),
        }
      : undefined,
    findingsCount: counts,
    assetsCount: assetTree.totalHosts,
    authorizedScope: [],
    executionEvents: mapEvents(detail),
    chainNodes: chain.nodes,
    chainEdges: chain.edges,
    assetTree,
    reportReady: Boolean(report.schema),
    backendState: String(detail.state || ''),
    report,
    reportMarkdown: String(detail.report_markdown || ''),
    workspace: asRecord(detail.workspace),
  };
  return { task, findings };
}

export async function loadControlPlane(): Promise<ControlPlaneSnapshot> {
  const [status, missions, tools, guard, settings, providers, workers] = await Promise.all([
    request<any>('/api/status'),
    request<any>('/api/missions'),
    request<any>('/api/tools'),
    request<any>('/api/guard'),
    request<any>('/api/settings'),
    request<any>('/api/ai/providers'),
    request<any>('/api/workers'),
  ]);
  const summaries = Array.isArray(missions.missions) ? missions.missions : [];
  const details = await Promise.all(
    summaries.map(async (summary: any) => {
      const detail = await request<MissionDetail>(`/api/missions/${encodeURIComponent(summary.id)}`);
      const [report, reportMarkdown] = await Promise.all([
        request<any>(`/api/missions/${encodeURIComponent(summary.id)}/report`).catch(() => ({})),
        fetch(`/api/missions/${encodeURIComponent(summary.id)}/report?format=md`, {
          headers: { Authorization: `Bearer ${savedToken()}` },
        }).then((response) => (response.ok ? response.text() : '')),
      ]);
      return missionToTask({ ...detail, report, report_markdown: reportMarkdown });
    }),
  );
  return {
    status,
    tasks: details.map((item) => item.task),
    findings: details.flatMap((item) => item.findings),
    tools,
    guard,
    settings,
    providers,
    workers,
  };
}

export const preflightMission = (target: string) => post<any>('/api/missions/preflight', { target });
export const startMission = (target: string) => post<any>('/api/missions/start', { target });
export const approveMission = (runId: string) => post<any>(`/api/missions/${encodeURIComponent(runId)}/approve`);
export const resumeMission = (runId: string) => post<any>(`/api/missions/${encodeURIComponent(runId)}/resume`);
export const addScope = (target: string) => post<any>('/api/scope/add', { target });
export const removeScope = (target: string) => post<any>('/api/scope/remove', { target });
export const updateAIConfig = (body: Record<string, unknown>) => post<any>('/api/ai/config', body);
export const saveProviderKey = (provider: string, value: string) =>
  post<any>(`/api/ai/providers/${encodeURIComponent(provider)}/key`, { value });
export const clearProviderKey = (provider: string) =>
  post<any>(`/api/ai/providers/${encodeURIComponent(provider)}/clear-key`);
export const probeProvider = (provider: string) =>
  post<any>(`/api/ai/providers/${encodeURIComponent(provider)}/probe`);
export const probeWorker = (worker: string) => post<any>(`/api/workers/${encodeURIComponent(worker)}/probe`);

export function mapWorkers(payload: Record<string, any>): WorkerNode[] {
  const workers = Array.isArray(payload.workers) ? payload.workers : [];
  return workers.map((worker: any) => {
    const probe = worker.last_probe;
    const ready = Boolean(probe?.ready);
    const inflight = Number(worker.scheduler?.inflight || 0);
    const status: WorkerNode['status'] = !probe || worker.enabled === false ? 'offline' : ready ? (inflight > 0 ? 'busy' : 'online') : 'offline';
    return {
      id: String(worker.id),
      name: String(worker.label || worker.name || worker.id),
      role: 'Scanner Worker',
      ip: String(worker.url || ''),
      location: String(worker.region || probe?.region || ''),
      status,
      cpuUsage: 0,
      memUsage: 0,
      activeTasks: inflight,
      latencyMs: Number(probe?.latency_ms || 0),
      installedTools: Object.entries(probe?.tools || {})
        .filter(([, value]: any) => value?.ready)
        .map(([name]) => name),
    };
  });
}