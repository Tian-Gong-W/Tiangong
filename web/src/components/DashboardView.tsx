import React from 'react';
import { Activity, AlertTriangle, ArrowRight, Plus, RefreshCw, ShieldCheck, Target, Wrench } from 'lucide-react';
import { Finding, Task } from '../types';

interface DashboardViewProps {
  tasks: Task[];
  findings: Finding[];
  status: Record<string, any>;
  tools: Record<string, any>;
  onSelectTask: (task: Task) => void;
  onApprove: (runId: string) => void;
  onOpenNewTaskModal: () => void;
  onNavigateFindings: () => void;
  onRefresh: () => void;
}

const Empty: React.FC<{ title: string; detail: string }> = ({ title, detail }) => (
  <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/50 p-10 text-center">
    <div className="text-sm font-bold text-slate-200">{title}</div>
    <div className="text-xs text-slate-500 mt-1">{detail}</div>
  </div>
);

export const DashboardView: React.FC<DashboardViewProps> = ({
  tasks,
  findings,
  status,
  tools,
  onSelectTask,
  onApprove,
  onOpenNewTaskModal,
  onNavigateFindings,
  onRefresh,
}) => {
  const running = tasks.filter((task) => task.status === 'running');
  const waiting = tasks.filter((task) => task.status === 'waiting_approval');
  const doctorReady = Boolean(status.doctor?.ready);
  const lead = status.lead_ai || {};

  return (
    <div className="flex-1 p-5 md:p-7 overflow-y-auto text-slate-100 space-y-5 max-w-7xl mx-auto z-10 relative">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold text-white">Tiangong 实时控制台</h1>
          <p className="text-xs text-slate-400 mt-1">版本 {status.version || '—'} · 数据来自当前后端工作区</p>
        </div>
        <div className="flex gap-2">
          <button onClick={onRefresh} className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs flex items-center gap-1.5"><RefreshCw className="w-3.5 h-3.5" />刷新</button>
          <button onClick={onOpenNewTaskModal} className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" />新建 Mission</button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[
          ['任务', tasks.length, Target, 'text-white'],
          ['运行中', running.length, Activity, 'text-cyan-300'],
          ['待批准', waiting.length, AlertTriangle, 'text-amber-300'],
          ['真实发现', findings.length, ShieldCheck, 'text-rose-300'],
          ['可用工具', `${tools.ready || 0}/${tools.count || 0}`, Wrench, doctorReady ? 'text-emerald-300' : 'text-amber-300'],
        ].map(([label, value, Icon, tone]: any) => (
          <div key={label} className="p-4 rounded-2xl bg-slate-900/85 border border-slate-800">
            <div className="text-[11px] text-slate-400 flex items-center justify-between"><span>{label}</span><Icon className={`w-3.5 h-3.5 ${tone}`} /></div>
            <div className={`text-2xl font-black font-mono mt-1 ${tone}`}>{value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-2xl bg-slate-900/85 border border-slate-800 p-5">
          <div className="text-xs font-bold text-white mb-4">后端就绪状态</div>
          <div className="grid sm:grid-cols-2 gap-2">
            {(status.doctor?.checks || []).map((check: any) => (
              <div key={check.name} className="rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-2.5 flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-mono text-slate-200">{check.name}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{check.detail}</div>
                </div>
                <span className={`text-[10px] font-bold ${check.ok ? 'text-emerald-400' : 'text-amber-400'}`}>{check.ok ? 'READY' : 'NOT READY'}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl bg-slate-900/85 border border-slate-800 p-5 space-y-3">
          <div className="text-xs font-bold text-white">AI Lead</div>
          <div className="text-2xl font-black">{lead.active ? '已启用' : '未启用'}</div>
          <div className="text-xs text-slate-400 font-mono">{lead.provider || 'disabled'} / {lead.model || '—'}</div>
          <div className="text-[11px] text-slate-500">Key: {lead.key_configured ? '已配置' : '未配置'} · 执行权限: 无</div>
        </div>
      </div>

      {waiting.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-xs font-bold text-amber-300">等待一次性批准</h2>
          {waiting.map((task) => (
            <div key={task.id} className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div>
                <div className="text-sm font-bold text-white">{task.name}</div>
                <div className="text-xs text-slate-400 mt-1">{task.pendingApproval?.description || '等待后端批准'}</div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => onSelectTask(task)} className="px-3 py-1.5 rounded-lg bg-slate-800 text-xs">详情</button>
                <button onClick={() => onApprove(task.id)} className="px-3 py-1.5 rounded-lg bg-amber-500 text-slate-950 text-xs font-bold">批准并继续</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold text-slate-300">Mission 记录</h2>
          {findings.length > 0 && <button onClick={onNavigateFindings} className="text-xs text-cyan-300">查看发现</button>}
        </div>
        {tasks.length === 0 ? (
          <Empty title="当前工作区没有 Mission" detail="这里保持为空；只有后端真正持久化的任务才会出现。" />
        ) : (
          <div className="grid md:grid-cols-2 gap-3">
            {tasks.slice(0, 8).map((task) => (
              <button key={task.id} onClick={() => onSelectTask(task)} className="text-left p-4 rounded-2xl bg-slate-900/85 border border-slate-800 hover:border-cyan-500/40">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-bold text-white truncate">{task.name}</div>
                  <span className="text-[10px] font-mono text-cyan-300">{task.backendState}</span>
                </div>
                <div className="text-xs font-mono text-slate-400 mt-2 truncate">{task.target}</div>
                <div className="flex justify-between text-[11px] text-slate-500 mt-3">
                  <span>{task.completedSteps}/{task.totalSteps} steps</span>
                  <span className="flex items-center gap-1 text-cyan-300">打开 <ArrowRight className="w-3 h-3" /></span>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
