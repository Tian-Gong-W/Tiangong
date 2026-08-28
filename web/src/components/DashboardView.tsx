import React from 'react';
import {
  Activity,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  Plus,
  Check,
  X,
  Target,
} from 'lucide-react';
import { Task, Finding } from '../types';

interface DashboardViewProps {
  tasks: Task[];
  findings: Finding[];
  onSelectTask: (task: Task) => void;
  onApprove: (approvalId: string) => void;
  onReject: (approvalId: string) => void;
  onOpenNewTaskModal: () => void;
  onNavigateFindings: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  tasks,
  findings,
  onSelectTask,
  onApprove,
  onReject,
  onOpenNewTaskModal,
  onNavigateFindings,
}) => {
  const runningTasks = tasks.filter((t) => t.status === 'running');
  const waitingTasks = tasks.filter((t) => t.status === 'waiting_approval' && t.pendingApproval);

  // Greeting based on time
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return '上午好，指挥官';
    if (hour < 18) return '下午好，指挥官';
    return '晚上好，指挥官';
  };

  return (
    <div className="flex-1 p-5 md:p-6 overflow-y-auto text-slate-100 space-y-4 max-w-7xl mx-auto z-10 relative">
      {/* 1. 指挥官问候与 S̶h̶e̶l̶l̶ R̴e̴n 运行状态栏 (紧凑高密度布局) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
              {getGreeting()}
            </h1>
            <span className="text-xs font-mono text-amber-300/90 px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/20">
              S̶h̶e̶l̶l̶ R̴e̴n 在席
            </span>
            <span className="text-xs text-slate-400 font-mono hidden md:inline-block">
              {new Date().toLocaleDateString('zh-CN', {
                month: 'long',
                day: 'numeric',
                weekday: 'long',
              })}
            </span>
          </div>
          <p className="text-xs text-slate-400">
            S̶h̶e̶l̶l̶ R̴e̴n 状态空间启发式引擎正在持续探索作战边界与漏洞链。
          </p>
        </div>

        {/* Quick New Task CTA Button */}
        <button
          onClick={onOpenNewTaskModal}
          className="px-3.5 py-2 rounded-xl bg-gradient-to-r from-amber-600 via-amber-500 to-amber-600 hover:from-amber-500 hover:to-amber-400 text-slate-950 text-xs font-bold transition-all shadow-md shadow-amber-950/30 flex items-center gap-1.5 self-start sm:self-auto shrink-0 cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5 text-slate-950 stroke-[2.5]" />
          下发新渗透作战
        </button>
      </div>

      {/* 2. 核心大盘指标条 (简约精炼，4个核心维度) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-2xl bg-slate-900/85 backdrop-blur-sm border border-slate-800/90 shadow-md">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>总计作战计划</span>
            <Target className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="text-2xl font-black font-mono text-white">{tasks.length}</div>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">全部部署目标</div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/85 backdrop-blur-sm border border-cyan-500/30 shadow-md">
          <div className="text-xs text-cyan-400 font-semibold mb-1 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
              S̶h̶e̶l̶l̶ R̴e̴n 活跃
            </span>
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
          </div>
          <div className="text-2xl font-black font-mono text-cyan-300">
            {runningTasks.length}
          </div>
          <div className="text-[11px] text-cyan-400/70 font-mono mt-0.5">自主推演推进中</div>
        </div>

        <div
          className={`p-4 rounded-2xl backdrop-blur-sm border shadow-md transition-all ${
            waitingTasks.length > 0
              ? 'bg-amber-950/30 border-amber-500/40 shadow-amber-950/20'
              : 'bg-slate-900/85 border-slate-800/90'
          }`}
        >
          <div className="text-xs mb-1 flex items-center justify-between">
            <span
              className={
                waitingTasks.length > 0 ? 'text-amber-300 font-bold' : 'text-slate-400'
              }
            >
              需指挥官授权
            </span>
            <ShieldAlert
              className={`w-3.5 h-3.5 ${
                waitingTasks.length > 0 ? 'text-amber-400' : 'text-slate-500'
              }`}
            />
          </div>
          <div
            className={`text-2xl font-black font-mono ${
              waitingTasks.length > 0 ? 'text-amber-300' : 'text-slate-300'
            }`}
          >
            {waitingTasks.length}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">
            {waitingTasks.length > 0 ? '越界/敏感操作阻断' : '在既定边界内运行'}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/85 backdrop-blur-sm border border-slate-800/90 shadow-md">
          <div className="text-xs text-slate-400 mb-1 flex items-center justify-between">
            <span>确证高危战果</span>
            <ShieldCheck className="w-3.5 h-3.5 text-rose-400" />
          </div>
          <div className="text-2xl font-black font-mono text-rose-400">
            {findings.length}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">
            100% 重现验证通过
          </div>
        </div>
      </div>

      {/* 3. 越界审批横幅 (仅在有待办时显示) */}
      {waitingTasks.length > 0 && (
        <div className="p-4 rounded-2xl bg-gradient-to-r from-amber-950/40 via-slate-900 to-slate-900 border border-amber-500/40 shadow-xl space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              S̶h̶e̶l̶l̶ R̴e̴n 敏感操作阻断（需要你的授权决策）
            </h2>
            <span className="text-[11px] font-mono text-slate-400">
              安全红线已触发挂起
            </span>
          </div>

          <div className="space-y-2.5">
            {waitingTasks.map((t) => {
              const appr = t.pendingApproval!;
              return (
                <div
                  key={appr.id}
                  className="p-3.5 rounded-xl bg-slate-950/80 border border-amber-500/30 flex flex-col md:flex-row md:items-center justify-between gap-3"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono">
                        {t.code}
                      </span>
                      <span className="text-xs font-bold text-white truncate">
                        {appr.taskName}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed max-w-2xl line-clamp-2">
                      {appr.description}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => onReject(appr.id)}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition-colors flex items-center gap-1"
                    >
                      <X className="w-3 h-3 text-slate-400" />
                      拒绝
                    </button>

                    <button
                      onClick={() => onApprove(appr.id)}
                      className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-colors flex items-center gap-1 shadow-md shadow-amber-950/50"
                    >
                      <Check className="w-3 h-3" />
                      批准放行
                    </button>

                    <button
                      onClick={() => onSelectTask(t)}
                      className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-cyan-400 text-xs font-semibold border border-slate-700 transition-colors"
                    >
                      作战室
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 4. 进行中的推演作战 (直接平铺展示) */}
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {runningTasks.map((task) => (
            <div
              key={task.id}
              onClick={() => onSelectTask(task)}
              className="p-5 rounded-2xl bg-slate-900/85 hover:bg-slate-900 backdrop-blur-sm border border-slate-800 hover:border-amber-500/40 transition-all duration-200 cursor-pointer shadow-lg hover:shadow-amber-950/20 group flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      {task.code}
                    </span>
                    <h3 className="text-sm font-bold text-white group-hover:text-amber-300 transition-colors truncate">
                      {task.name}
                    </h3>
                  </div>

                  <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1 shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                    S̶h̶e̶l̶l̶ R̴e̴n 运行
                  </span>
                </div>

                <div className="text-xs text-slate-400 font-mono mb-3">
                  目标: <span className="text-slate-200">{task.target}</span>
                </div>

                {/* Progress Bar */}
                <div className="space-y-1 mb-3">
                  <div className="flex justify-between text-[11px] font-mono">
                    <span className="text-slate-400">
                      推演进度 ({task.completedSteps}/{task.totalSteps} 步骤)
                    </span>
                    <span className="text-amber-300 font-bold">{task.progress}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                    <div
                      className="h-full bg-gradient-to-r from-amber-500 to-emerald-400 rounded-full"
                      style={{ width: `${task.progress}%` }}
                    />
                  </div>
                </div>

                <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800/80 text-xs">
                  <span className="text-[10px] text-amber-400 font-mono block mb-0.5">
                    正在推进:
                  </span>
                  <p className="text-slate-300 line-clamp-1 font-medium">
                    {task.currentAction}
                  </p>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                <div className="flex items-center gap-3 font-mono text-[11px]">
                  <span>
                    发现: <strong className="text-rose-400">{task.findingsCount.critical + task.findingsCount.high}</strong>
                  </span>
                  <span>·</span>
                  <span>
                    资产: <strong className="text-slate-200">{task.assetsCount}</strong>
                  </span>
                </div>

                <span className="text-amber-300 group-hover:translate-x-1 transition-transform flex items-center gap-1 text-xs font-semibold">
                  进入作战室 <ArrowRight className="w-3.5 h-3.5" />
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* 确证漏洞战果 */}
        <div className="bg-slate-900/85 backdrop-blur-sm border border-slate-800 rounded-2xl overflow-hidden shadow-xl divide-y divide-slate-800/80">
          {findings.map((f) => (
            <div
              key={f.id}
              onClick={onNavigateFindings}
              className="p-4 hover:bg-slate-800/50 transition-colors cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span
                  className={`text-xs font-bold px-2 py-0.5 rounded font-mono shrink-0 ${
                    f.severity === 'CRITICAL'
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                      : f.severity === 'HIGH'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                  }`}
                >
                  {f.severity}
                </span>

                <div className="min-w-0">
                  <div className="text-sm font-bold text-white truncate">
                    {f.title}
                  </div>
                  <div className="text-xs text-slate-400 font-mono truncate mt-0.5">
                    影响目标: <span className="text-amber-300">{f.affectedAsset}</span> · 任务: {f.taskName}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0 text-xs font-mono">
                <span className="text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> 100% 重现验证
                </span>
                <span className="text-slate-500 hidden md:inline">
                  {f.discoveryTime.split(' ')[1]}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
