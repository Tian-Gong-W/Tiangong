import React from 'react';
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Plus,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Target,
  Wrench,
} from 'lucide-react';
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
  const runningTasks = tasks.filter((task) => task.status === 'running');
  const waitingTasks = tasks.filter((task) => task.status === 'waiting_approval' && task.pendingApproval);
  const confirmedFindings = findings.filter((finding) => finding.status === 'confirmed');
  const doctorReady = Boolean(status.doctor?.ready);
  const lead = status.lead_ai || {};
  const toolList = Array.isArray(tools.tools) ? tools.tools : [];
  const readyTools = typeof tools.ready === 'number' ? tools.ready : toolList.filter((tool: any) => tool.available).length;
  const totalTools = typeof tools.count === 'number' ? tools.count : toolList.length;

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return '上午好，指挥官';
    if (hour < 18) return '下午好，指挥官';
    return '晚上好，指挥官';
  };

  return (
    <div className="flex-1 p-5 md:p-6 overflow-y-auto text-slate-100 space-y-4 max-w-7xl mx-auto z-10 relative">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-lg font-bold text-white tracking-tight">{getGreeting()}</h1>
            <span className={`text-xs font-mono px-2 py-0.5 rounded-md border ${doctorReady ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20' : 'text-amber-300 bg-amber-500/10 border-amber-500/20'}`}>
              Tiangong {doctorReady ? 'Ready' : 'Degraded'}
            </span>
            <span className="text-xs text-slate-400 font-mono hidden md:inline-block">
              {status.version ? `v${status.version}` : '版本未知'}
            </span>
          </div>
          <p className="text-xs text-slate-400">控制台只显示当前后端工作区、工具注册表、AI 与 Mission 的真实状态。</p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
          <button onClick={onRefresh} className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs flex items-center gap-1.5">
            <RefreshCw className="w-3.5 h-3.5" />刷新
          </button>
          <button onClick={onOpenNewTaskModal} className="px-3.5 py-2 rounded-xl bg-gradient-to-r from-amber-600 via-amber-500 to-amber-600 hover:from-amber-500 hover:to-amber-400 text-slate-950 text-xs font-bold transition-all shadow-md shadow-amber-950/30 flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5 stroke-[2.5]" />下发新 Mission
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
        <div className="p-4 rounded-2xl bg-slate-900/85 border border-slate-800/90 shadow-md">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between"><span>Mission</span><Target className="w-3.5 h-3.5 text-amber-400" /></div>
          <div className="text-2xl font-black font-mono text-white">{tasks.length}</div>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">Chronicle 真实记录</div>
        </div>
        <div className="p-4 rounded-2xl bg-slate-900/85 border border-cyan-500/30 shadow-md">
          <div className="text-xs text-cyan-400 font-semibold mb-1 flex items-center justify-between"><span className="flex items-center gap-1.5"><span className={`w-2 h-2 rounded-full bg-cyan-400 ${runningTasks.length ? 'animate-ping' : ''}`} />运行中</span><Activity className="w-3.5 h-3.5 text-cyan-400" /></div>
          <div className="text-2xl font-black font-mono text-cyan-300">{runningTasks.length}</div>
          <div className="text-[11px] text-cyan-400/70 font-mono mt-0.5">实时执行状态</div>
        </div>
        <div className={`p-4 rounded-2xl border shadow-md ${waitingTasks.length ? 'bg-amber-950/30 border-amber-500/40' : 'bg-slate-900/85 border-slate-800/90'}`}>
          <div className="text-xs mb-1 flex items-center justify-between"><span className={waitingTasks.length ? 'text-amber-300 font-bold' : 'text-slate-400'}>待批准</span><ShieldAlert className={`w-3.5 h-3.5 ${waitingTasks.length ? 'text-amber-400' : 'text-slate-500'}`} /></div>
          <div className={`text-2xl font-black font-mono ${waitingTasks.length ? 'text-amber-300' : 'text-slate-300'}`}>{waitingTasks.length}</div>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">一次性授权动作</div>
        </div>
        <button onClick={onNavigateFindings} className="text-left p-4 rounded-2xl bg-slate-900/85 border border-slate-800/90 hover:border-rose-500/30 shadow-md">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between"><span>已确证发现</span><ShieldCheck className="w-3.5 h-3.5 text-rose-400" /></div>
          <div className="text-2xl font-black font-mono text-rose-400">{confirmedFindings.length}</div>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">仅证据状态 confirmed</div>
        </button>
        <div className="p-4 rounded-2xl bg-slate-900/85 border border-slate-800/90 shadow-md col-span-2 md:col-span-1">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between"><span>工具就绪</span><Wrench className="w-3.5 h-3.5 text-emerald-400" /></div>
          <div className="text-2xl font-black font-mono text-emerald-300">{readyTools}/{totalTools}</div>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">Registry readiness</div>
        </div>
      </div>

      {waitingTasks.length > 0 && (
        <div className="p-4 rounded-2xl bg-gradient-to-r from-amber-950/40 via-slate-900 to-slate-900 border border-amber-500/40 shadow-xl space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />需要一次性授权</h2>
            <span className="text-[11px] font-mono text-slate-400">Guard 已暂停对应动作</span>
          </div>
          <div className="space-y-2.5">
            {waitingTasks.map((task) => (
              <div key={task.id} className="p-3.5 rounded-xl bg-slate-950/80 border border-amber-500/30 flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2"><span className="text-xs font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono">{task.code}</span><span className="text-xs font-bold text-white truncate">{task.name}</span></div>
                  <p className="text-xs text-slate-300 leading-relaxed max-w-2xl line-clamp-2">{task.pendingApproval?.description || '后端未提供批准说明'}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => onSelectTask(task)} className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-cyan-400 text-xs font-semibold border border-slate-700">作战室</button>
                  <button onClick={() => onApprove(task.id)} className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold">批准放行</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between"><h2 className="text-xs font-bold text-slate-300">Mission 记录</h2><span className="text-[11px] text-slate-500">{tasks.length} total</span></div>
          {tasks.length === 0 ? (
            <Empty title="当前工作区没有 Mission" detail="不会生成示例任务；后端有持久化记录后这里才会出现。" />
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {tasks.slice(0, 8).map((task) => (
                <button key={task.id} onClick={() => onSelectTask(task)} className="text-left p-5 rounded-2xl bg-slate-900/85 hover:bg-slate-900 border border-slate-800 hover:border-amber-500/40 transition-all shadow-lg group">
                  <div className="flex items-center justify-between gap-2 mb-2.5"><div className="flex items-center gap-2 min-w-0"><span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">{task.code}</span><h3 className="text-sm font-bold text-white group-hover:text-amber-300 truncate">{task.name}</h3></div><span className="text-[10px] font-mono text-cyan-300 shrink-0">{task.backendState || task.status}</span></div>
                  <div className="text-xs text-slate-400 font-mono mb-3">目标: <span className="text-slate-200">{task.target}</span></div>
                  <div className="space-y-1 mb-3"><div className="flex justify-between text-[11px] font-mono"><span className="text-slate-400">{task.completedSteps}/{task.totalSteps} steps</span><span className="text-amber-300 font-bold">{task.progress}%</span></div><div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800"><div className="h-full bg-gradient-to-r from-amber-500 to-emerald-400 rounded-full" style={{ width: `${task.progress}%` }} /></div></div>
                  <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800/80 text-xs"><span className="text-[10px] text-amber-400 font-mono block mb-0.5">当前记录</span><p className="text-slate-300 line-clamp-1 font-medium">{task.currentAction || '后端没有当前动作记录'}</p></div>
                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400"><span className="font-mono text-[11px]">资产 {task.assetsCount} · 发现 {task.findingsCount.critical + task.findingsCount.high + task.findingsCount.medium + task.findingsCount.low}</span><span className="text-amber-300 group-hover:translate-x-1 transition-transform flex items-center gap-1 font-semibold">进入作战室 <ArrowRight className="w-3.5 h-3.5" /></span></div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl bg-slate-900/85 border border-slate-800 p-5 space-y-3">
            <div className="text-xs font-bold text-white">AI Lead</div>
            <div className="text-xl font-black">{lead.active ? '已启用' : '未启用'}</div>
            <div className="text-xs text-slate-400 font-mono">{lead.provider || 'Not configured'}{lead.model ? ` / ${lead.model}` : ''}</div>
            <div className="text-[11px] text-slate-500">Key: {lead.key_configured ? '已配置' : '未配置'} · 执行权限由后端 authority 决定</div>
          </div>
          <div className="rounded-2xl bg-slate-900/85 border border-slate-800 p-5">
            <div className="text-xs font-bold text-white mb-3">后端检查</div>
            <div className="space-y-2 max-h-64 overflow-auto">
              {(status.doctor?.checks || []).length === 0 ? <div className="text-xs text-slate-500">没有检查记录</div> : (status.doctor?.checks || []).map((check: any) => (
                <div key={check.name} className="rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-2.5 flex items-start justify-between gap-3"><div><div className="text-xs font-mono text-slate-200">{check.name}</div><div className="text-[10px] text-slate-500 mt-0.5">{check.detail}</div></div><span className={`text-[10px] font-bold ${check.ok ? 'text-emerald-400' : 'text-amber-400'}`}>{check.ok ? 'READY' : 'NOT READY'}</span></div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="bg-slate-900/85 border border-slate-800 rounded-2xl overflow-hidden shadow-xl divide-y divide-slate-800/80">
        <div className="px-4 py-3 flex items-center justify-between"><h2 className="text-xs font-bold text-slate-300">发现与证据</h2>{findings.length > 0 && <button onClick={onNavigateFindings} className="text-xs text-cyan-300">查看全部</button>}</div>
        {findings.length === 0 ? <div className="p-8 text-center text-xs text-slate-500">没有实际发现</div> : findings.slice(0, 8).map((finding) => (
          <button key={finding.id} onClick={onNavigateFindings} className="w-full p-4 hover:bg-slate-800/50 transition-colors text-left flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0"><span className={`text-xs font-bold px-2 py-0.5 rounded font-mono shrink-0 ${finding.severity === 'CRITICAL' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : finding.severity === 'HIGH' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'}`}>{finding.severity}</span><div className="min-w-0"><div className="text-sm font-bold text-white truncate">{finding.title}</div><div className="text-xs text-slate-400 font-mono truncate mt-0.5">{finding.affectedAsset || '未记录资产'} · {finding.taskName}</div></div></div>
            <span className={`text-xs font-mono flex items-center gap-1 shrink-0 ${finding.status === 'confirmed' ? 'text-emerald-400' : 'text-amber-300'}`}><CheckCircle2 className="w-3.5 h-3.5" />{finding.status === 'confirmed' ? '证据确认' : '候选结果'}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
