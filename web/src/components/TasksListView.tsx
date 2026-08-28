import React, { useState } from 'react';
import { ArrowRight, Play, Plus, Search, Target } from 'lucide-react';
import { Task } from '../types';

interface TasksListViewProps {
  tasks: Task[];
  onSelectTask: (task: Task) => void;
  onOpenNewTaskModal: () => void;
  onResume: (taskId: string) => void;
}

export const TasksListView: React.FC<TasksListViewProps> = ({ tasks, onSelectTask, onOpenNewTaskModal, onResume }) => {
  const [query, setQuery] = useState('');
  const filtered = tasks.filter((task) => [task.name, task.target, task.code].some((value) => value.toLowerCase().includes(query.toLowerCase())));
  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto text-slate-100 space-y-5 max-w-7xl mx-auto">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div><h1 className="text-xl font-bold flex items-center gap-2"><Target className="w-4 h-4 text-cyan-400" />Mission 中心</h1><p className="text-xs text-slate-400 mt-1">仅显示 Chronicle 中的真实任务记录</p></div>
        <button onClick={onOpenNewTaskModal} className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-xs font-bold flex items-center gap-1.5"><Plus className="w-4 h-4" />新建</button>
      </div>
      <div className="relative max-w-sm"><Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索任务或目标" className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs outline-none focus:border-cyan-500" /></div>
      {filtered.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-dashed border-slate-700 bg-slate-900/40"><div className="text-sm text-slate-300">没有任务记录</div><div className="text-xs text-slate-500 mt-1">后端为空时这里不会生成示例任务。</div></div>
      ) : (
        <div className="space-y-3">
          {filtered.map((task) => (
            <div key={task.id} className="p-5 rounded-2xl bg-slate-900/85 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <button onClick={() => onSelectTask(task)} className="text-left flex-1 min-w-0">
                <div className="flex items-center gap-2"><span className="text-xs font-mono text-cyan-300">{task.code}</span><span className="text-sm font-bold truncate">{task.name}</span><span className="text-[10px] font-mono text-slate-400">{task.backendState}</span></div>
                <div className="text-xs text-slate-400 mt-2 font-mono">{task.target}</div>
                <div className="text-[11px] text-slate-500 mt-2">{task.completedSteps}/{task.totalSteps} 步 · {task.executionEvents.length} 条执行记录 · {task.assetsCount} 个观测资产</div>
              </button>
              <div className="flex gap-2">
                {task.status === 'running' && task.progress < 100 && (
                  <button onClick={() => onResume(task.id)} className="px-3 py-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-1"><Play className="w-3 h-3" />恢复预算暂停任务</button>
                )}
                <button onClick={() => onSelectTask(task)} className="px-3 py-1.5 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-xs flex items-center gap-1">详情 <ArrowRight className="w-3 h-3" /></button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
