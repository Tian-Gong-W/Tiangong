import React from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, Clock, Layers, Server, ShieldCheck, Terminal } from 'lucide-react';
import { Task, TaskTabId } from '../../types';

interface OverviewTabProps {
  task: Task;
  onApprove?: (runId: string) => void;
  onSwitchTab?: (tabId: TaskTabId) => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({ task, onApprove, onSwitchTab }) => (
  <div className="space-y-5 max-w-6xl mx-auto">
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {[
        ['后端状态', task.backendState || task.status, Server],
        ['执行步骤', `${task.completedSteps}/${task.totalSteps}`, CheckCircle2],
        ['观测资产', task.assetsCount, Layers],
        ['运行时间', `${task.runtimeMinutes} 分钟`, Clock],
      ].map(([label, value, Icon]: any) => <div key={label} className="p-4 rounded-2xl bg-slate-900 border border-slate-800"><div className="text-[11px] text-slate-500 flex items-center gap-1.5"><Icon className="w-3.5 h-3.5" />{label}</div><div className="text-lg font-bold mt-2">{value}</div></div>)}
    </div>
    <div className="grid md:grid-cols-2 gap-4">
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800"><div className="text-xs font-bold text-cyan-300">当前记录</div><div className="text-sm text-slate-300 mt-3">{task.currentAction || '后端没有当前动作记录'}</div><button onClick={() => onSwitchTab?.('execution')} className="text-xs text-cyan-300 flex items-center gap-1 mt-4">查看执行证据 <ArrowRight className="w-3 h-3" /></button></div>
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800"><div className="text-xs font-bold text-purple-300">下一步</div><div className="text-sm text-slate-300 mt-3">{task.nextAction || '后端没有排队中的下一步'}</div><button onClick={() => onSwitchTab?.('chain')} className="text-xs text-purple-300 flex items-center gap-1 mt-4">查看探索链 <ArrowRight className="w-3 h-3" /></button></div>
    </div>
    {task.pendingApproval ? <div className="p-5 rounded-2xl bg-amber-950/25 border border-amber-500/40 flex flex-col md:flex-row md:items-center justify-between gap-4"><div><div className="text-sm font-bold text-amber-300 flex items-center gap-1.5"><AlertTriangle className="w-4 h-4" />{task.pendingApproval.title}</div><div className="text-xs text-slate-300 mt-2">{task.pendingApproval.description}</div><div className="text-[11px] font-mono text-slate-500 mt-1">{task.pendingApproval.target}</div></div><button onClick={() => onApprove?.(task.id)} className="px-4 py-2 rounded-xl bg-amber-500 text-slate-950 text-xs font-black">批准一次性 Grant</button></div> : <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 text-xs text-slate-500 flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-emerald-400" />当前没有待批准动作。这不代表任务拥有无限授权。</div>}
    {task.executionEvents.length === 0 && <div className="p-10 text-center rounded-2xl border border-dashed border-slate-700 text-sm text-slate-500"><Terminal className="w-6 h-6 mx-auto mb-2" />尚无执行记录</div>}
  </div>
);
