import React from 'react';
import { RefreshCw, Server, Wrench } from 'lucide-react';
import { ExecutionNode } from '../types';

interface NodesGlobalViewProps {
  nodes: ExecutionNode[];
  tools: any[];
  executionMode: string;
  onProbe: (id: string) => Promise<void>;
}

export const NodesGlobalView: React.FC<NodesGlobalViewProps> = ({ nodes, tools, executionMode, onProbe }) => {
  const readyTools = tools.filter((tool) => Boolean(tool.available)).length;
  const emptyWorkerText = executionMode === 'worker'
    ? '后端处于 worker 执行模式，但当前没有返回可用 Worker 节点。'
    : '当前使用本地执行模式，不显示模拟 Worker 节点。';

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto text-slate-100 space-y-6 max-w-7xl mx-auto">
      <div className="border-b border-slate-800 pb-4">
        <h1 className="text-xl font-bold flex items-center gap-2"><Server className="w-4 h-4 text-cyan-400" />执行节点与工具</h1>
        <p className="text-xs text-slate-400 mt-1">执行模式：{executionMode || '未返回'} · Worker 与工具状态均来自 Tiangong 后端</p>
      </div>

      <section className="space-y-3">
        <h2 className="text-xs font-bold text-slate-300">Worker Fleet ({nodes.length})</h2>
        {nodes.length === 0 ? (
          <div className="p-10 text-center rounded-2xl border border-dashed border-slate-700 bg-slate-900/40">
            <div className="text-sm text-slate-300">没有 Worker 记录</div>
            <div className="text-xs text-slate-500 mt-1">{emptyWorkerText}</div>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-3">
            {nodes.map((node) => (
              <div key={node.id} className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
                <div className="flex justify-between gap-3">
                  <div>
                    <div className="font-bold">{node.name}</div>
                    <div className="text-xs font-mono text-slate-500 mt-1">{node.ip || '地址未返回'} · {node.location || 'region 未配置'}</div>
                  </div>
                  <span className={`text-[10px] font-bold ${node.status === 'online' ? 'text-emerald-400' : node.status === 'busy' ? 'text-amber-400' : 'text-slate-500'}`}>{node.status.toUpperCase()}</span>
                </div>
                <div className="text-xs text-slate-400">inflight: {node.activeTasks} · ready tools: {node.installedTools.length}</div>
                <button onClick={() => onProbe(node.id)} className="px-3 py-1.5 rounded-lg bg-slate-800 text-xs flex items-center gap-1"><RefreshCw className="w-3 h-3" />主动探测</button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-bold text-slate-300">本地 Tool Registry ({readyTools}/{tools.length} ready)</h2>
        {tools.length === 0 ? (
          <div className="p-8 text-center rounded-2xl border border-dashed border-slate-700 text-xs text-slate-500">工具注册表为空</div>
        ) : (
          <div className="grid md:grid-cols-3 gap-3">
            {tools.map((tool) => (
              <div key={tool.name} className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
                <div className="flex justify-between gap-3">
                  <span className="font-mono text-sm flex items-center gap-1.5"><Wrench className="w-3.5 h-3.5 text-cyan-400" />{tool.name}</span>
                  <span className={`text-[10px] font-bold ${tool.available ? 'text-emerald-400' : 'text-amber-400'}`}>{tool.available ? 'READY' : 'NOT READY'}</span>
                </div>
                <div className="text-xs text-slate-500 mt-2">{tool.description || '后端未返回描述'}</div>
                {!tool.available && <div className="text-[10px] text-amber-300 mt-3">{tool.readiness?.detail || '后端未返回就绪详情'}</div>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
