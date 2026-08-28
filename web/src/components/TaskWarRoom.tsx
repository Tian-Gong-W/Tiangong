import React, { useState } from 'react';
import {
  ArrowLeft,
  Play,
  Pause,
  Square,
  AlertCircle,
  Activity,
  Terminal,
  GitCommit,
  ShieldAlert,
  Layers,
  FileText,
  ShieldCheck,
  Zap,
  Sliders,
  CheckCircle2,
  Clock,
  Sparkles,
} from 'lucide-react';
import { Task, TaskTabId, Finding } from '../types';
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
  onTogglePause: (taskId: string) => void;
  onTerminateTask: (taskId: string) => void;
  onApprove: (approvalId: string) => void;
  onReject: (approvalId: string) => void;
  onOpenInterventionModal: (task: Task) => void;
}

export const TaskWarRoom: React.FC<TaskWarRoomProps> = ({
  task,
  allFindings,
  onBack,
  onTogglePause,
  onTerminateTask,
  onApprove,
  onReject,
  onOpenInterventionModal,
}) => {
  const [activeTab, setActiveTab] = useState<TaskTabId>('overview');
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [selectedTraceFindingId, setSelectedTraceFindingId] = useState<string | null>(null);

  // Filter findings for this task
  const taskFindings = allFindings.filter((f) => f.taskId === task.id);
  const isRunning = task.status === 'running';

  const handleJumpToEvidence = (evidenceId: string) => {
    setSelectedEvidenceId(evidenceId);
    setActiveTab('findings');
  };

  const handleJumpToFinding = (findingId: string) => {
    setActiveTab('findings');
  };

  const handleTraceInExecution = (findingId: string) => {
    setSelectedTraceFindingId(findingId);
    setActiveTab('execution');
  };

  const tabs = [
    { id: 'overview' as TaskTabId, name: '总览', enName: 'Overview', icon: Activity },
    {
      id: 'execution' as TaskTabId,
      name: '执行过程',
      enName: 'Execution',
      icon: Terminal,
      count: task.executionEvents?.length,
    },
    { id: 'chain' as TaskTabId, name: '探索链', enName: 'Exploration Chain', icon: GitCommit },
    {
      id: 'findings' as TaskTabId,
      name: '发现',
      enName: 'Findings',
      icon: ShieldAlert,
      badge: taskFindings.length > 0 ? `${taskFindings.length}` : undefined,
    },
    { id: 'assets' as TaskTabId, name: '资产', enName: 'Assets', icon: Layers },
    { id: 'report' as TaskTabId, name: '报告', enName: 'Report', icon: FileText },
  ];

  return (
    <div className="flex-1 flex flex-col h-screen bg-slate-950 text-slate-100 overflow-hidden select-none">
      {/* 1. 顶部常驻区 (Fixed Header - 铁打的营盘，常驻显示名称、目标、状态、授权与主控按钮) */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-lg shrink-0 z-20">
        <div className="flex items-center gap-4 min-w-0">
          <button
            onClick={onBack}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700 shrink-0"
            title="返回任务列表"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>

          <div className="min-w-0">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                {task.type === 'RedTeam'
                  ? '红蓝对抗'
                  : task.type === 'ApiAudit'
                  ? 'API 审计'
                  : '漏洞评估'}
              </span>

              <h1 className="text-base font-bold text-white tracking-wide truncate">
                {task.name}
              </h1>

              <span className="text-xs font-mono text-slate-400">
                {task.code}
              </span>
            </div>

            <div className="flex items-center gap-3 text-xs text-slate-400 mt-1 font-mono flex-wrap">
              <span>目标: <strong className="text-slate-200">{task.target}</strong></span>
              <span className="hidden sm:inline text-slate-600">|</span>
              <span className="text-slate-300">
                当前阶段: <span className="text-cyan-300 font-semibold">{task.currentStage}</span>
              </span>
              <span className="hidden sm:inline text-slate-600">|</span>
              <span>耗时: {task.runtimeMinutes} 分钟</span>
            </div>
          </div>
        </div>

        {/* Top Control Bar & State Capsule */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Authorization Grant Status */}
          <div className="hidden lg:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-950/80 border border-slate-800 text-xs">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-300 font-mono text-[11px]">
              {task.pendingApproval ? '授权拦截：待确认' : '授权状态：本任务已批准'}
            </span>
          </div>

          {/* Machine State Indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-950 border border-slate-800 text-xs shadow-inner">
            <span
              className={`w-2 h-2 rounded-full ${
                isRunning
                  ? 'bg-emerald-400 animate-ping'
                  : task.status === 'waiting_approval'
                  ? 'bg-amber-400 animate-bounce'
                  : 'bg-slate-400'
              }`}
            />
            <span className="text-slate-200 font-medium text-xs">
              {isRunning
                ? 'AI 独立推理中'
                : task.status === 'waiting_approval'
                ? '等待审批 (需放行)'
                : task.status === 'paused'
                ? '已暂停'
                : '任务已完成'}
            </span>
          </div>

          {/* Control Buttons (Pause / Resume / Intervene / Terminate) */}
          <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => onTogglePause(task.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm ${
                isRunning
                  ? 'bg-cyan-600 hover:bg-cyan-500 text-white'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white'
              }`}
            >
              {isRunning ? (
                <>
                  <Pause className="w-3.5 h-3.5" /> 暂停任务
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" /> 恢复执行
                </>
              )}
            </button>

            <button
              onClick={() => onOpenInterventionModal(task)}
              className="p-1.5 hover:bg-slate-800 text-slate-300 hover:text-cyan-300 rounded-lg text-xs transition-colors flex items-center gap-1 px-2.5"
              title="下发专家指令进行人工干预"
            >
              <Sliders className="w-3.5 h-3.5" />
              <span className="hidden sm:inline text-[11px]">指令干预</span>
            </button>

            <button
              onClick={() => onTerminateTask(task.id)}
              className="p-1.5 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 rounded-lg transition-colors"
              title="强制终止任务"
            >
              <Square className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* 2. 场景化 Tab 导航栏 (按作战心智 6 大主页签) */}
      <div className="bg-slate-900/60 border-b border-slate-800 px-6 flex gap-1 sm:gap-4 shrink-0 overflow-x-auto">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              onClick={() => {
                setActiveTab(tab.id);
                if (tab.id !== 'findings') setSelectedEvidenceId(null);
              }}
              className={`py-3 px-2 sm:px-3 text-xs sm:text-sm font-semibold flex items-center gap-2 border-b-2 transition-all relative whitespace-nowrap ${
                isActive
                  ? 'border-cyan-400 text-cyan-300 font-bold'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon
                className={`w-4 h-4 transition-colors ${
                  isActive ? 'text-cyan-400' : 'text-slate-500'
                }`}
              />
              <span>{tab.name}</span>

              {tab.badge && (
                <span className="text-[10px] font-mono bg-rose-500/20 text-rose-300 border border-rose-500/40 px-1.5 py-0.2 rounded-full font-bold">
                  {tab.badge}
                </span>
              )}

              {tab.count !== undefined && tab.count > 0 && (
                <span className="text-[10px] font-mono text-slate-500">
                  ({tab.count})
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* 3. 标签页对应的内容面板区 */}
      <div className="flex-1 p-4 sm:p-6 overflow-y-auto bg-slate-950">
        {activeTab === 'overview' && (
          <OverviewTab
            task={task}
            onApprove={onApprove}
            onReject={onReject}
            onSwitchTab={(t) => setActiveTab(t)}
          />
        )}

        {activeTab === 'execution' && (
          <ExecutionTab
            events={task.executionEvents}
            findings={taskFindings}
            onViewEvidence={handleJumpToEvidence}
            initialSelectedFindingId={selectedTraceFindingId}
          />
        )}

        {activeTab === 'chain' && (
          <ExplorationChainTab
            nodes={task.chainNodes}
            edges={task.chainEdges}
            onViewEvidence={handleJumpToEvidence}
          />
        )}

        {activeTab === 'findings' && (
          <FindingsEvidenceTab
            findings={taskFindings}
            highlightEvidenceId={selectedEvidenceId}
            onTraceInExecution={handleTraceInExecution}
          />
        )}

        {activeTab === 'assets' && (
          <AssetsTopologyTab
            assetTree={task.assetTree}
            onViewFinding={handleJumpToFinding}
          />
        )}

        {activeTab === 'report' && (
          <ReportTab task={task} findings={taskFindings} />
        )}
      </div>
    </div>
  );
};
