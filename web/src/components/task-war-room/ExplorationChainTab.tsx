import React, { useMemo, useState } from 'react';
import { BrainCircuit, GitBranch, KeyRound, SearchCheck, ShieldCheck, Target } from 'lucide-react';
import { ChainEdge, ChainNode } from '../../types';

interface ExplorationChainTabProps {
  nodes: ChainNode[];
  edges: ChainEdge[];
  onViewEvidence?: (evidenceId: string) => void;
}

export const ExplorationChainTab: React.FC<ExplorationChainTabProps> = ({ nodes, edges, onViewEvidence }) => {
  const [selectedId, setSelectedId] = useState(nodes[0]?.id || '');
  const selected = useMemo(() => nodes.find((node) => node.id === selectedId) || nodes[0], [nodes, selectedId]);
  const summary = useMemo(() => ({
    targets: nodes.filter((node) => node.type === 'target').length,
    intents: nodes.filter((node) => node.type === 'probe').length,
    facts: nodes.filter((node) => node.type === 'tech' && node.status === 'confirmed').length,
    decisions: nodes.filter((node) => node.type === 'reasoning').length,
    findings: nodes.filter((node) => node.type === 'vulnerability' && node.status === 'confirmed').length,
  }), [nodes]);
  const frontier = useMemo(
    () => nodes.filter((node) => node.type === 'probe' && ['active', 'pending', 'alert'].includes(node.status)),
    [nodes],
  );

  if (nodes.length === 0) return <div className="p-12 text-center rounded-2xl border border-dashed border-slate-700 text-sm text-slate-500"><GitBranch className="w-7 h-7 mx-auto mb-2" />后端尚未生成探索图节点</div>;

  return (
    <div className="space-y-4 max-w-6xl mx-auto">
      <div className="p-4 rounded-2xl bg-slate-900/75 border border-slate-800 space-y-3">
        <div>
          <div className="text-xs font-bold text-white">Fact / Intent 探索面</div>
          <div className="text-[11px] text-slate-500 mt-1">这里展示 Tiangong 后端已经投影出的目标、探索意图、证据事实与推理关系；页面本身不创建事实。</div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          {[
            ['目标', summary.targets, Target],
            ['探索意图', summary.intents, GitBranch],
            ['已确认事实', summary.facts, SearchCheck],
            ['推理节点', summary.decisions, BrainCircuit],
            ['已确认发现', summary.findings, ShieldCheck],
          ].map(([label, value, Icon]: any) => (
            <div key={label} className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
              <div className="text-[10px] text-slate-500 flex items-center gap-1.5"><Icon className="w-3 h-3" />{label}</div>
              <div className="text-lg font-black font-mono mt-1">{value}</div>
            </div>
          ))}
        </div>
        <div className="rounded-xl bg-slate-950/70 border border-slate-800 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">当前 Frontier</div>
          {frontier.length === 0 ? (
            <div className="text-xs text-slate-500 mt-2">没有开放的探索意图；如 Mission 尚未结束，应以后端 reasoning / stop reason 判断为何停止，而不是由页面补造下一步。</div>
          ) : (
            <div className="flex flex-wrap gap-2 mt-2">
              {frontier.map((node) => (
                <button key={node.id} onClick={() => setSelectedId(node.id)} className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-[11px] text-slate-300 hover:border-cyan-500/50">
                  {node.label} · {node.status}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
          <div className="text-xs font-bold text-slate-300 mb-4">Mission workspace exploration · {nodes.length} nodes / {edges.length} edges</div>
          {nodes.map((node) => {
            const incoming = edges.filter((edge) => edge.to === node.id);
            return <button key={node.id} onClick={() => setSelectedId(node.id)} className={`w-full text-left p-3.5 rounded-xl border flex items-center justify-between gap-3 ${selected?.id === node.id ? 'bg-slate-900 border-cyan-500/50' : 'bg-slate-950/50 border-slate-800'}`}><div><div className="text-sm font-bold text-white">{node.label}</div><div className="text-[11px] text-slate-500 mt-1">{node.subLabel || node.type}{incoming.length ? ` · ${incoming.map((edge) => edge.label).filter(Boolean).join(', ')}` : ''}</div></div><span className={`text-[10px] font-bold ${node.status === 'confirmed' ? 'text-emerald-400' : node.status === 'alert' ? 'text-rose-400' : 'text-amber-400'}`}>{node.status}</span></button>;
          })}
        </div>
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
          {selected ? <div className="space-y-4"><div><div className="text-[10px] font-mono text-cyan-300">{selected.type}</div><h2 className="text-base font-bold mt-1">{selected.label}</h2></div><div className="text-xs text-slate-400 leading-relaxed">{selected.details || '该节点没有更多后端元数据。'}</div><div className="text-xs text-slate-500">状态：{selected.status}{selected.severity ? ` · 严重度 ${selected.severity}` : ''}</div>{selected.evidenceId && <button onClick={() => onViewEvidence?.(selected.evidenceId!)} className="w-full py-2 rounded-xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-xs flex items-center justify-center gap-1.5"><KeyRound className="w-3.5 h-3.5" />查看证据 {selected.evidenceId}</button>}<div className="pt-3 border-t border-slate-800 text-[10px] text-slate-500">图谱为后端只读投影；页面不创建事实、不改变计划。</div></div> : null}
        </div>
      </div>
    </div>
  );
};
