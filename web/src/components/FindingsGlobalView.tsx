import React, { useEffect, useState } from 'react';
import { ExternalLink, FileCheck, Search, ShieldAlert } from 'lucide-react';
import { Finding } from '../types';

interface FindingsGlobalViewProps {
  findings: Finding[];
  onSelectFindingTask?: (taskId: string) => void;
}

export const FindingsGlobalView: React.FC<FindingsGlobalViewProps> = ({ findings, onSelectFindingTask }) => {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Finding | null>(findings[0] || null);
  useEffect(() => {
    if (selected && !findings.some((item) => item.id === selected.id)) setSelected(findings[0] || null);
    if (!selected && findings.length) setSelected(findings[0]);
  }, [findings, selected]);
  const filtered = findings.filter((item) => [item.title, item.affectedAsset, item.cve || ''].some((value) => value.toLowerCase().includes(query.toLowerCase())));
  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto text-slate-100 space-y-5 max-w-7xl mx-auto">
      <div className="border-b border-slate-800 pb-4"><h1 className="text-xl font-bold flex items-center gap-2"><ShieldAlert className="w-4 h-4 text-rose-400" />发现与证据</h1><p className="text-xs text-slate-400 mt-1">来自报告聚合器的实际匹配；没有匹配时保持为空</p></div>
      <div className="relative max-w-sm"><Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索发现、CVE 或资产" className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs outline-none" /></div>
      {findings.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-dashed border-slate-700 bg-slate-900/40"><FileCheck className="w-7 h-7 mx-auto text-slate-600" /><div className="text-sm text-slate-300 mt-3">没有实际发现</div><div className="text-xs text-slate-500 mt-1">未收到 Nuclei 聚合结果，不显示示例漏洞。</div></div>
      ) : (
        <div className="grid lg:grid-cols-5 gap-4">
          <div className="lg:col-span-2 space-y-2">
            {filtered.map((item) => (
              <button key={item.id} onClick={() => setSelected(item)} className={`w-full text-left p-4 rounded-xl border ${selected?.id === item.id ? 'bg-slate-900 border-cyan-500/50' : 'bg-slate-900/60 border-slate-800'}`}>
                <div className="flex justify-between gap-2"><span className="text-sm font-bold text-white">{item.title}</span><span className="text-[10px] font-bold text-rose-300">{item.severity}</span></div>
                <div className="text-xs font-mono text-slate-500 mt-2">{item.affectedAsset}</div>
                <div className={`text-[10px] mt-2 ${item.status === 'confirmed' ? 'text-emerald-400' : 'text-amber-400'}`}>{item.status === 'confirmed' ? '证据确认' : '候选结果'}</div>
              </button>
            ))}
          </div>
          <div className="lg:col-span-3">
            {selected && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/85 p-6 space-y-4">
                <div><h2 className="text-lg font-bold">{selected.title}</h2><div className="text-xs font-mono text-cyan-300 mt-1">{selected.affectedUrl || selected.affectedAsset}</div></div>
                <div className="grid sm:grid-cols-3 gap-2 text-xs">
                  <div className="p-3 bg-slate-950 rounded-xl"><span className="text-slate-500 block">严重度</span><strong>{selected.severity}</strong></div>
                  <div className="p-3 bg-slate-950 rounded-xl"><span className="text-slate-500 block">证据状态</span><strong>{selected.verification.method}</strong></div>
                  <div className="p-3 bg-slate-950 rounded-xl"><span className="text-slate-500 block">归因状态</span><strong>{selected.verification.antiHallucinationCheck}</strong></div>
                </div>
                {selected.summary && <p className="text-sm text-slate-300 leading-relaxed">{selected.summary}</p>}
                <div><div className="text-xs font-bold mb-2">证据记录 ({selected.evidenceList.length})</div>{selected.evidenceList.length ? selected.evidenceList.map((proof) => <pre key={proof.id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] whitespace-pre-wrap overflow-auto max-h-52">{proof.content || '无文本输出'}</pre>) : <div className="text-xs text-slate-500">无关联证据记录</div>}</div>
                <button onClick={() => onSelectFindingTask?.(selected.taskId)} className="text-xs text-cyan-300 flex items-center gap-1">打开所属 Mission <ExternalLink className="w-3 h-3" /></button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
