import React, { useEffect, useState } from 'react';
import { FileCheck, Terminal } from 'lucide-react';
import { Finding } from '../../types';

interface FindingsEvidenceTabProps {
  findings: Finding[];
  highlightEvidenceId?: string | null;
  onTraceInExecution?: (findingId: string) => void;
}

export const FindingsEvidenceTab: React.FC<FindingsEvidenceTabProps> = ({ findings, highlightEvidenceId, onTraceInExecution }) => {
  const [selectedId, setSelectedId] = useState(findings[0]?.id || '');
  useEffect(() => {
    if (!findings.some((item) => item.id === selectedId)) setSelectedId(findings[0]?.id || '');
  }, [findings, selectedId]);
  const selected = findings.find((item) => item.id === selectedId) || findings[0];
  if (!selected) return <div className="p-12 text-center rounded-2xl border border-dashed border-slate-700 text-sm text-slate-500"><FileCheck className="w-7 h-7 mx-auto mb-2" />没有实际发现或证据</div>;
  return (
    <div className="grid lg:grid-cols-5 gap-4 max-w-6xl mx-auto">
      <div className="lg:col-span-2 space-y-2">{findings.map((item) => <button key={item.id} onClick={() => setSelectedId(item.id)} className={`w-full text-left p-4 rounded-xl border ${selected.id === item.id ? 'bg-slate-900 border-cyan-500/50' : 'bg-slate-900/50 border-slate-800'}`}><div className="flex justify-between gap-2"><span className="text-sm font-bold">{item.title}</span><span className="text-[10px] text-rose-300">{item.severity}</span></div><div className="text-xs font-mono text-slate-500 mt-2">{item.affectedAsset}</div><div className={`text-[10px] mt-2 ${item.status === 'confirmed' ? 'text-emerald-400' : 'text-amber-400'}`}>{item.status}</div></button>)}</div>
      <div className="lg:col-span-3 p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div><h2 className="text-base font-bold">{selected.title}</h2><div className="text-xs text-cyan-300 font-mono mt-1">{selected.affectedUrl || selected.affectedAsset}</div></div>
        <div className="grid grid-cols-2 gap-2 text-xs"><div className="p-3 rounded-xl bg-slate-950"><span className="text-slate-500 block">Evidence</span>{selected.verification.method}</div><div className="p-3 rounded-xl bg-slate-950"><span className="text-slate-500 block">Attribution</span>{selected.verification.antiHallucinationCheck}</div></div>
        {selected.summary && <p className="text-xs text-slate-300 leading-relaxed">{selected.summary}</p>}
        <div className="space-y-2"><div className="text-xs font-bold">证据 ({selected.evidenceList.length})</div>{selected.evidenceList.length ? selected.evidenceList.map((proof) => <div key={proof.id} className={`rounded-xl border p-3 ${highlightEvidenceId === proof.id ? 'border-cyan-400 bg-cyan-950/20' : 'border-slate-800 bg-slate-950'}`}><div className="text-[10px] text-slate-500 font-mono mb-2">{proof.id} · {proof.timestamp}</div><pre className="text-[11px] whitespace-pre-wrap overflow-auto max-h-56">{proof.content || '无文本输出'}</pre></div>) : <div className="text-xs text-slate-500">无证据记录</div>}</div>
        <button onClick={() => onTraceInExecution?.(selected.id)} className="px-3 py-2 rounded-xl bg-slate-800 text-xs flex items-center gap-1.5"><Terminal className="w-3.5 h-3.5" />查看执行步骤</button>
      </div>
    </div>
  );
};
