import React, { useState } from 'react';
import { Activity, ArrowLeft, FileText, GitCommit, Layers, ShieldAlert, Terminal } from 'lucide-react';
import { Finding, Task, TaskTabId } from '../types';
import { OverviewTab } from './task-war-room/OverviewTab';
import { ExecutionTab } from './task-war-room/ExecutionTab';
import { ExplorationChainTab } from './task-war-room/ExplorationChainTab';
import { FindingsEvidenceTab } from './task-war-room/FindingsEvidenceTab';
import { AssetsTopologyTab } from './task-war-room/AssetsTopologyTab';
import { ReportTab } from './task-war-room/ReportTab';

interface TaskWarRoomProps {
  task: Task;
  allFindings: Finding[];
  onBack: () => void;
  onApprove: (runId: string) => void;
}

export const TaskWarRoom: React.FC<TaskWarRoomProps> = ({ task, allFindings, onBack, onApprove }) => {
  const [activeTab, setActiveTab] = useState<TaskTabId>('overview');
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const findings = allFindings.filter((item) => item.taskId === task.id);
  const confirmedFindings = findings.filter((item) => item.status === 'confirmed');
  const tabs = [
    ['overview', '总览', Activity],
    ['execution', '执行记录', Terminal],
    ['chain', '探索链', GitCommit],
    ['findings', '发现', ShieldAlert],
    ['assets', '资产', Layers],
    ['report', '报告', FileText],
  ] as const;

  return (
    <div className="flex-1 flex flex-col h-screen bg-slate-950 overflow-hidden">
      <header className="bg-slate-900 border-b border-slate-800 px-5 py-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button onClick={onBack} className="p-2 rounded-lg bg-slate-800 text-slate-300"><ArrowLeft className="w-4 h-4" /></button>
          <div className="min-w-0">
            <div className="flex items-center gap-2"><h1 className="text-base font-bold truncate">{task.name}</h1><span className="text-[10px] font-mono text-cyan-300">{task.backendState || '—'}</span></div>
            <div className="text-xs text-slate-400 font-mono mt-1 truncate">{task.target} · {task.code}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">{task.completedSteps}/{task.totalSteps} steps · {task.runtimeMinutes} min</span>
          {task.pendingApproval && <button onClick={() => onApprove(task.id)} className="px-3 py-2 rounded-xl bg-amber-500 text-slate-950 text-xs font-black">批准并继续</button>}
        </div>
      </header>

      <div className="bg-slate-900/60 border-b border-slate-800 px-5 flex gap-2 overflow-x-auto">
        {tabs.map(([id, label, Icon]) => (
          <button key={id} onClick={() => setActiveTab(id)} className={`py-3 px-3 text-xs flex items-center gap-1.5 border-b-2 whitespace-nowrap ${activeTab === id ? 'border-cyan-400 text-cyan-300' : 'border-transparent text-slate-400'}`}>
            <Icon className="w-3.5 h-3.5" />{label}{id === 'findings' && findings.length > 0 ? ` (${findings.length})` : ''}
          </button>
        ))}
      </div>

      <div className="flex-1 p-4 sm:p-6 overflow-y-auto">
        {activeTab === 'overview' && <OverviewTab task={task} onApprove={onApprove} onSwitchTab={setActiveTab as any} />}
        {activeTab === 'execution' && <ExecutionTab events={task.executionEvents} findings={confirmedFindings} onViewEvidence={(id) => { setEvidenceId(id); setActiveTab('findings'); }} />}
        {activeTab === 'chain' && <ExplorationChainTab nodes={task.chainNodes} edges={task.chainEdges} onViewEvidence={(id) => { setEvidenceId(id); setActiveTab('findings'); }} />}
        {activeTab === 'findings' && <FindingsEvidenceTab findings={findings} highlightEvidenceId={evidenceId} onTraceInExecution={() => setActiveTab('execution')} />}
        {activeTab === 'assets' && <AssetsTopologyTab assetTree={task.assetTree} onViewFinding={() => setActiveTab('findings')} />}
        {activeTab === 'report' && <ReportTab task={task} findings={findings} />}
      </div>
    </div>
  );
};
