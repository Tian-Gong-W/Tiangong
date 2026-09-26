import React from 'react';
import { ArrowRight, Boxes, Network, Server } from 'lucide-react';
import { Task } from '../types';

interface AssetsGlobalViewProps {
  tasks: Task[];
  onSelectTask: (task: Task) => void;
}

export const AssetsGlobalView: React.FC<AssetsGlobalViewProps> = ({ tasks, onSelectTask }) => {
  const assets = tasks.flatMap((task) => task.assetTree.hosts.map((host) => ({ task, host })));
  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto text-slate-100 space-y-5 max-w-7xl mx-auto">
      <div className="border-b border-slate-800 pb-4"><h1 className="text-xl font-bold flex items-center gap-2"><Network className="w-4 h-4 text-cyan-400" />资产观测</h1><p className="text-xs text-slate-400 mt-1">根据 Mission workspace 的解析、扫描和服务事实投影；不补造拓扑。</p></div>
      <div className="grid grid-cols-3 gap-3">
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800"><div className="text-xs text-slate-500">Mission 目标</div><div className="text-2xl font-black mt-1">{tasks.length}</div></div>
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800"><div className="text-xs text-slate-500">观测主机</div><div className="text-2xl font-black mt-1">{assets.length}</div></div>
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800"><div className="text-xs text-slate-500">观测服务</div><div className="text-2xl font-black mt-1">{assets.reduce((sum, item) => sum + item.host.services.length, 0)}</div></div>
      </div>
      {assets.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-dashed border-slate-700 bg-slate-900/40"><Boxes className="w-7 h-7 mx-auto text-slate-600" /><div className="text-sm text-slate-300 mt-3">没有资产观测</div><div className="text-xs text-slate-500 mt-1">后端尚未产生已解析或已扫描的资产事实。</div></div>
      ) : (
        <div className="grid md:grid-cols-2 gap-3">
          {assets.map(({ task, host }) => (
            <button key={`${task.id}:${host.ip}`} onClick={() => onSelectTask(task)} className="text-left p-5 rounded-2xl bg-slate-900/85 border border-slate-800 hover:border-cyan-500/40">
              <div className="flex items-center justify-between"><span className="font-mono text-sm text-white flex items-center gap-2"><Server className="w-4 h-4 text-cyan-400" />{host.ip}</span><span className="text-[10px] text-slate-400">{host.status}</span></div>
              <div className="mt-3 flex flex-wrap gap-1.5">{host.services.length ? host.services.map((service) => <span key={`${service.port}/${service.protocol}`} className="text-[10px] font-mono px-2 py-1 rounded bg-slate-950 border border-slate-800">{service.port}/{service.protocol} {service.service}</span>) : <span className="text-xs text-slate-500">无服务事实</span>}</div>
              <div className="mt-4 text-[11px] text-cyan-300 flex items-center gap-1">来源：{task.code} <ArrowRight className="w-3 h-3" /></div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
