import React, { useState } from 'react';
import {
  Target,
  Search,
  Plus,
  Play,
  Pause,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowRight,
  ShieldCheck,
  Filter,
} from 'lucide-react';
import { Task, TaskStatus } from '../types';

interface TasksListViewProps {
  tasks: Task[];
  onSelectTask: (task: Task) => void;
  onOpenNewTaskModal: () => void;
  onTogglePause: (taskId: string) => void;
}

export const TasksListView: React.FC<TasksListViewProps> = ({
  tasks,
  onSelectTask,
  onOpenNewTaskModal,
  onTogglePause,
}) => {
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filteredTasks = tasks.filter((t) => {
    const matchStatus =
      filterStatus === 'all'
        ? true
        : filterStatus === 'running'
        ? t.status === 'running'
        : filterStatus === 'waiting_approval'
        ? t.status === 'waiting_approval'
        : t.status === 'completed';

    const matchSearch =
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.target.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.code.toLowerCase().includes(searchQuery.toLowerCase());

    return matchStatus && matchSearch;
  });

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-slate-950 text-slate-100 space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Target className="w-4 h-4 text-cyan-400" />
            <h1 className="text-xl font-bold text-white tracking-wide">
              任务中心 (Task Center)
            </h1>
          </div>
          <p className="text-xs text-slate-400">
            统筹管理所有自动化渗透任务生命周期，点击任务直接进入独立作战指挥室
          </p>
        </div>

        <button
          onClick={onOpenNewTaskModal}
          className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition-all shadow-md flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          新建任务
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900/90 border border-slate-800 rounded-xl p-3">
        <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto">
          {[
            { id: 'all', label: '全部任务', count: tasks.length },
            {
              id: 'running',
              label: '运行中',
              count: tasks.filter((t) => t.status === 'running').length,
            },
            {
              id: 'waiting_approval',
              label: '待审批',
              count: tasks.filter((t) => t.status === 'waiting_approval').length,
            },
            {
              id: 'completed',
              label: '已完成',
              count: tasks.filter((t) => t.status === 'completed').length,
            },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterStatus(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
                filterStatus === tab.id
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {tab.label} ({tab.count})
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="搜索任务名称、目标或编号..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
      </div>

      {/* Task Cards List */}
      <div className="space-y-3">
        {filteredTasks.map((task) => {
          const isRunning = task.status === 'running';

          return (
            <div
              key={task.id}
              className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-cyan-500/40 transition-all duration-150 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-lg group"
            >
              <div
                onClick={() => onSelectTask(task)}
                className="space-y-2 cursor-pointer flex-1 min-w-0"
              >
                <div className="flex items-center gap-2.5 flex-wrap">
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                    {task.code}
                  </span>

                  <h3 className="text-sm font-bold text-white group-hover:text-cyan-300 transition-colors truncate">
                    {task.name}
                  </h3>

                  <span
                    className={`text-[11px] font-mono px-2 py-0.5 rounded-full flex items-center gap-1 ${
                      isRunning
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : task.status === 'waiting_approval'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        isRunning
                          ? 'bg-emerald-400 animate-ping'
                          : task.status === 'waiting_approval'
                          ? 'bg-amber-400'
                          : 'bg-slate-500'
                      }`}
                    />
                    {isRunning
                      ? '执行中'
                      : task.status === 'waiting_approval'
                      ? '等待人工审批'
                      : '已完成'}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-xs text-slate-400 font-mono flex-wrap">
                  <span>目标: <strong className="text-slate-200">{task.target}</strong></span>
                  <span>阶段: <strong className="text-cyan-300">{task.currentStage}</strong></span>
                  <span>节点: {task.assignedNode.split(' ')[0]}</span>
                </div>

                {/* Progress bar */}
                <div className="w-full max-w-md pt-1">
                  <div className="flex justify-between text-[10px] font-mono text-slate-400 mb-1">
                    <span>进度 {task.completedSteps}/{task.totalSteps}</span>
                    <span className="text-cyan-300 font-bold">{task.progress}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                    <div
                      className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 rounded-full"
                      style={{ width: `${task.progress}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-3 shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-slate-800">
                <button
                  onClick={() => onTogglePause(task.id)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition-colors flex items-center gap-1"
                >
                  {isRunning ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                  {isRunning ? '暂停' : '恢复'}
                </button>

                <button
                  onClick={() => onSelectTask(task)}
                  className="px-4 py-1.5 rounded-lg bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/40 text-xs font-bold transition-colors flex items-center gap-1.5 shadow-sm"
                >
                  进入作战室 <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
