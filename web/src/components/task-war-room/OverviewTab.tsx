import React from 'react';
import {
  Activity,
  CheckCircle2,
  Clock,
  Cpu,
  Server,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
  Zap,
  Check,
  X,
  Target,
  Sparkles,
} from 'lucide-react';
import { Task, PendingApproval } from '../../types';

interface OverviewTabProps {
  task: Task;
  onApprove?: (approvalId: string) => void;
  onReject?: (approvalId: string) => void;
  onSwitchTab?: (tabId: 'execution' | 'chain' | 'findings' | 'assets' | 'report') => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  task,
  onApprove,
  onReject,
  onSwitchTab,
}) => {
  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-10">
      {/* 1. 一屏回答：现在怎么样？ (Core Metrics Grid) */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-5 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <h2 className="text-base font-bold text-white tracking-wide">
              当前态势概览
            </h2>
            <span className="text-xs text-slate-400 font-mono">
              一屏掌握任务核心状态与进展
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-slate-400">推进度:</span>
            <div className="w-36 h-2 bg-slate-800 rounded-full overflow-hidden border border-slate-700">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 rounded-full transition-all duration-500"
                style={{ width: `${task.progress}%` }}
              />
            </div>
            <span className="text-xs font-mono font-bold text-cyan-300">
              {task.progress}%
            </span>
          </div>
        </div>

        {/* 6 Key Indicators */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3.5">
            <div className="text-[11px] text-slate-400 mb-1 flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-cyan-400" />
              当前状态
            </div>
            <div className="text-sm font-bold text-white flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  task.status === 'running'
                    ? 'bg-emerald-400 animate-ping'
                    : task.status === 'waiting_approval'
                    ? 'bg-amber-400'
                    : 'bg-slate-400'
                }`}
              />
              {task.status === 'running'
                ? '执行中'
                : task.status === 'waiting_approval'
                ? '等待审批'
                : task.status === 'paused'
                ? '已暂停'
                : '已完成'}
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3.5">
            <div className="text-[11px] text-slate-400 mb-1 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              任务进度
            </div>
            <div className="text-sm font-bold font-mono text-white">
              {task.completedSteps} / {task.totalSteps}{' '}
              <span className="text-xs text-slate-400 font-normal">步骤</span>
            </div>
          </div>

          <div
            onClick={() => onSwitchTab?.('findings')}
            className="bg-slate-950/60 border border-slate-800/80 hover:border-rose-500/40 rounded-xl p-3.5 cursor-pointer transition-colors group"
          >
            <div className="text-[11px] text-slate-400 mb-1 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                确认发现
              </span>
              <span className="text-[10px] text-cyan-400 group-hover:underline">查看</span>
            </div>
            <div className="text-sm font-bold font-mono text-rose-400 flex items-center gap-2">
              <span>{task.findingsCount.critical + task.findingsCount.high + task.findingsCount.medium}</span>
              <div className="flex gap-1 text-[10px] font-sans">
                {task.findingsCount.critical > 0 && (
                  <span className="px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                    {task.findingsCount.critical} 严重
                  </span>
                )}
                {task.findingsCount.high > 0 && (
                  <span className="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    {task.findingsCount.high} 高危
                  </span>
                )}
              </div>
            </div>
          </div>

          <div
            onClick={() => onSwitchTab?.('assets')}
            className="bg-slate-950/60 border border-slate-800/80 hover:border-cyan-500/40 rounded-xl p-3.5 cursor-pointer transition-colors group"
          >
            <div className="text-[11px] text-slate-400 mb-1 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-blue-400" />
                覆盖资产
              </span>
              <span className="text-[10px] text-cyan-400 group-hover:underline">拓扑</span>
            </div>
            <div className="text-sm font-bold font-mono text-white">
              {task.assetsCount}{' '}
              <span className="text-xs text-slate-400 font-normal">目标主机</span>
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3.5">
            <div className="text-[11px] text-slate-400 mb-1 flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5 text-purple-400" />
              执行节点
            </div>
            <div className="text-xs font-semibold text-slate-200 truncate" title={task.assignedNode}>
              {task.assignedNode.split(' ')[0]}
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3.5">
            <div className="text-[11px] text-slate-400 mb-1 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              运行时间
            </div>
            <div className="text-sm font-bold font-mono text-slate-200">
              {task.runtimeMinutes} <span className="text-xs text-slate-400 font-normal">分钟</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. 下方简洁行动面板：当前正在做 / 下一步 / 需要你处理 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* 当前正在做 */}
        <div className="bg-slate-900/80 border border-cyan-500/30 rounded-2xl p-5 relative overflow-hidden flex flex-col justify-between">
          <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/5 rounded-full blur-2xl pointer-events-none" />
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                当前正在做
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                {task.currentStage}
              </span>
            </div>
            <p className="text-sm text-slate-200 font-medium leading-relaxed">
              {task.currentAction}
            </p>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
            <span className="font-mono">AI 自主推理决策树 #4</span>
            <button
              onClick={() => onSwitchTab?.('execution')}
              className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
            >
              实时日志 <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* 下一步计划 */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                下一步推演
              </span>
              <span className="text-[11px] font-mono text-slate-500">
                自动排队中
              </span>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed">
              {task.nextAction}
            </p>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
            <span>策略红线：已启用</span>
            <button
              onClick={() => onSwitchTab?.('chain')}
              className="text-purple-400 hover:text-purple-300 flex items-center gap-1 transition-colors"
            >
              探索链图谱 <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* 需要你处理 (内敛型审批卡片) */}
        <div
          className={`rounded-2xl p-5 flex flex-col justify-between transition-all ${
            task.pendingApproval
              ? 'bg-gradient-to-b from-amber-950/40 to-slate-900/90 border border-amber-500/40 shadow-lg shadow-amber-950/30'
              : 'bg-slate-900/80 border border-slate-800'
          }`}
        >
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck
                  className={`w-4 h-4 ${
                    task.pendingApproval ? 'text-amber-400' : 'text-emerald-400'
                  }`}
                />
                <span
                  className={
                    task.pendingApproval ? 'text-amber-300' : 'text-slate-400'
                  }
                >
                  需要你处理
                </span>
              </span>

              {task.pendingApproval ? (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse">
                  1 项待确认
                </span>
              ) : (
                <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                  <Check className="w-3 h-3" />
                  无卡点
                </span>
              )}
            </div>

            {task.pendingApproval ? (
              <div className="space-y-2">
                <div className="text-xs font-bold text-white">
                  {task.pendingApproval.title}
                </div>
                <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                  {task.pendingApproval.description}
                </p>
                <div className="p-2 rounded bg-slate-950/80 border border-amber-500/20 text-[11px] font-mono text-amber-200 truncate">
                  目标: {task.pendingApproval.target}
                </div>
              </div>
            ) : (
              <div className="py-2 text-xs text-slate-400 leading-relaxed">
                本任务已获得完全授权，当前所有探测动作均在已批准范围内正常运行，无需人工干预。
              </div>
            )}
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80">
            {task.pendingApproval ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => onReject?.(task.pendingApproval!.id)}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition-colors flex items-center justify-center gap-1"
                >
                  <X className="w-3.5 h-3.5" /> 拒绝
                </button>
                <button
                  onClick={() => onApprove?.(task.pendingApproval!.id)}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-colors flex items-center justify-center gap-1 shadow-sm"
                >
                  <Check className="w-3.5 h-3.5" /> 允许继续
                </button>
              </div>
            ) : (
              <div className="text-[11px] text-slate-500 flex items-center justify-between">
                <span>授权边界: 正常</span>
                <span className="text-emerald-400 font-mono">Mission Grant: OK</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
