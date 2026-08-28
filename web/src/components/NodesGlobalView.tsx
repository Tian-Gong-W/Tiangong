import React from 'react';
import {
  Server,
  Activity,
  CheckCircle2,
  Cpu,
  Zap,
  Shield,
  Terminal,
  RefreshCw,
  Plus,
} from 'lucide-react';
import { ExecutionNode } from '../types';

interface NodesGlobalViewProps {
  nodes: ExecutionNode[];
}

export const NodesGlobalView: React.FC<NodesGlobalViewProps> = ({ nodes }) => {
  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-slate-950 text-slate-100 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Server className="w-4 h-4 text-cyan-400" />
            <h1 className="text-xl font-bold text-white tracking-wide">
              执行节点与工具池 (Nodes & Tools)
            </h1>
          </div>
          <p className="text-xs text-slate-400">
            分布式攻防执行探针、内网 C2 枢纽与工具运行环境状态
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-mono">
            在线 Worker: {nodes.filter((n) => n.status === 'online').length}/{nodes.length}
          </span>
        </div>
      </div>

      {/* Nodes Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {nodes.map((node) => (
          <div
            key={node.id}
            className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                  <Server className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">{node.name}</h3>
                  <span className="text-xs text-slate-400 font-mono">
                    {node.ip} · {node.region}
                  </span>
                </div>
              </div>

              <span
                className={`text-[11px] font-mono px-2 py-0.5 rounded-full flex items-center gap-1 ${
                  node.status === 'online'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                }`}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                {node.status === 'online' ? '运行就绪' : '离线'}
              </span>
            </div>

            {/* Performance Stats */}
            <div className="grid grid-cols-3 gap-2 p-3 bg-slate-950 rounded-xl border border-slate-800/80 text-xs font-mono text-center">
              <div>
                <span className="text-[10px] text-slate-500 block">CPU 负载</span>
                <span className="text-slate-200 font-bold">{node.cpuUsage}%</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 block">内存占用</span>
                <span className="text-slate-200 font-bold">{node.memUsage}%</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 block">当前运行任务</span>
                <span className="text-cyan-300 font-bold">{node.activeTasks}</span>
              </div>
            </div>

            {/* Installed Toolset Tags */}
            <div>
              <span className="text-[11px] font-semibold text-slate-400 block mb-2">
                已挂载工具套件：
              </span>
              <div className="flex flex-wrap gap-1.5">
                {node.tools.map((tool) => (
                  <span
                    key={tool}
                    className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
