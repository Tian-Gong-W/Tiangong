export type NavId = 'dashboard' | 'tasks' | 'findings' | 'assets' | 'ai' | 'nodes' | 'settings';
export type NavItemId = NavId;

export type TaskTabId = 'overview' | 'execution' | 'chain' | 'findings' | 'assets' | 'report';

export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type TaskStatus = 'running' | 'waiting_approval' | 'paused' | 'completed' | 'failed';

export type TaskType = 'RedTeam' | 'VulnAssess' | 'ApiAudit' | 'CloudBreach';

export interface EvidenceItem {
  id: string;
  type: 'credential' | 'file' | 'screenshot' | 'poc' | 'response';
  title: string;
  timestamp: string;
  target: string;
  content: string;
  metadata?: Record<string, string>;
  isVerified: boolean;
}

export interface VerificationProof {
  verified: boolean;
  verifiedAt: string;
  method: string;
  reproducibilityRate?: number;
  antiHallucinationCheck: string;
  verifierWorker: string;
}

export interface Finding {
  id: string;
  taskId: string;
  taskName: string;
  title: string;
  severity: SeverityLevel;
  status: 'confirmed' | 'verifying' | 'candidate';
  affectedAsset: string;
  affectedUrl: string;
  cve?: string;
  cvss?: number;
  discoveryTime: string;
  summary: string;
  impact: string;
  verification: VerificationProof;
  evidenceList: EvidenceItem[];
  pocCommand: string;
  remediation: string;
  aiJudgment: string;
}

export interface NetworkTrace {
  method: string;
  url: string;
  headers?: Record<string, string>;
  requestBody?: string;
  responseCode?: number;
  responseHeaders?: Record<string, string>;
  responseBody?: string;
  assertionMatch?: string;
}

export interface WorkerTrace {
  workerId: string;
  containerSandbox?: string;
  command: string;
  exitCode: number;
  executionTimeMs: number;
  memoryDelta?: string;
  assertionPassed?: boolean;
  verificationLogicSummary?: string;
}

export interface ExecutionEvent {
  id: string;
  timestamp: string;
  timeDisplay: string;
  title: string;
  phase: 'recon' | 'fingerprint' | 'ai_reasoning' | 'vuln_verify' | 'exploit' | 'post_exploit';
  status: 'completed' | 'running' | 'pending' | 'failed';
  tool: string;
  target: string;
  duration: string;
  workerNode: string;
  outputSummary: string;
  rawOutput: string;
  evidenceId?: string;
  payload?: string;
  findingId?: string;
  findingIds?: string[];
  traceType?: 'initial_discovery' | 'ai_secondary_verification' | 'post_exploitation' | 'recon';
  networkTrace?: NetworkTrace;
  workerTrace?: WorkerTrace;
}

export interface ChainNode {
  id: string;
  label: string;
  subLabel?: string;
  type: 'target' | 'service' | 'tech' | 'reasoning' | 'probe' | 'vulnerability' | 'exploit' | 'privilege';
  status: 'confirmed' | 'active' | 'pending' | 'alert';
  parentId?: string;
  details?: string;
  evidenceId?: string;
  severity?: SeverityLevel;
}

export interface ChainEdge {
  from: string;
  to: string;
  label?: string;
  animated?: boolean;
}

export interface AssetService {
  port: number;
  protocol: string;
  service: string;
  version?: string;
  status: 'checked' | 'unchecked' | 'need_auth' | 'has_vuln';
  findingIds: string[];
}

export interface AssetHost {
  ip: string;
  hostname?: string;
  os?: string;
  status: 'checked' | 'unchecked' | 'need_auth' | 'has_vuln';
  services: AssetService[];
}

export interface AssetDomain {
  id: string;
  domain: string;
  scopeStatus: 'in_scope' | 'expanded' | 'pending_approval';
  totalHosts: number;
  checkedHosts: number;
  hosts: AssetHost[];
}

export interface PendingApproval {
  id: string;
  taskId: string;
  taskName: string;
  title: string;
  description: string;
  target: string;
  requestedAction: string;
  requestedScope: string;
  riskLevel: 'HIGH' | 'CRITICAL' | 'MEDIUM';
  timestamp: string;
  proposedCommand: string;
  reason: string;
}

export interface Task {
  id: string;
  code: string; // e.g. #Task-202603
  name: string;
  target: string;
  type: 'RedTeam' | 'VulnAssess' | 'ApiAudit' | 'CloudBreach';
  status: TaskStatus;
  progress: number; // 0 - 100
  totalSteps: number;
  completedSteps: number;
  assignedNode: string;
  runtimeMinutes: number;
  startTime: string;
  currentStage: string;
  currentAction: string;
  nextAction: string;
  actionRequired: boolean;
  pendingApproval?: PendingApproval;
  findingsCount: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  assetsCount: number;
  authorizedScope: string[];
  executionEvents: ExecutionEvent[];
  chainNodes: ChainNode[];
  chainEdges: ChainEdge[];
  assetTree: AssetDomain;
  reportReady: boolean;
  backendState?: string;
  report?: Record<string, any>;
  reportMarkdown?: string;
  workspace?: Record<string, any>;
}

export interface WorkerNode {
  id: string;
  name: string;
  role: 'C2 Control' | 'Scanner Worker' | 'AI Inference Node' | 'Cloud Edge';
  ip: string;
  location: string;
  status: 'online' | 'busy' | 'offline';
  cpuUsage: number;
  memUsage: number;
  activeTasks: number;
  latencyMs: number;
  installedTools: string[];
}

export type ExecutionNode = WorkerNode;

export type MissionDetail = Record<string, any>;

export interface ControlPlaneSnapshot {
  status: Record<string, any>;
  tasks: Task[];
  findings: Finding[];
  tools: Record<string, any>;
  guard: Record<string, any>;
  settings: Record<string, any>;
  providers: Record<string, any>;
  workers: Record<string, any>;
}
