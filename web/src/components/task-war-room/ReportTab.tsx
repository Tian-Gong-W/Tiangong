import React, { useState } from 'react';
import { Check, Copy, Download, FileText } from 'lucide-react';
import { Finding, Task } from '../../types';

interface ReportTabProps {
  task: Task;
  findings: Finding[];
}

export const ReportTab: React.FC<ReportTabProps> = ({ task }) => {
  const [copied, setCopied] = useState(false);
  const markdown = task.reportMarkdown || '';
  const json = task.report || {};
  const download = (format: 'md' | 'json') => {
    const value = format === 'md' ? markdown : JSON.stringify(json, null, 2);
    const blob = new Blob([value], { type: format === 'md' ? 'text/markdown' : 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `tonmen-${task.id}.${format}`;
    link.click();
    URL.revokeObjectURL(link.href);
  };
  if (!task.reportReady) return <div className="p-12 text-center rounded-2xl border border-dashed border-slate-700 text-sm text-slate-500"><FileText className="w-7 h-7 mx-auto mb-2" />后端尚未生成报告</div>;
  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><h2 className="text-sm font-bold">Tiangong 后端报告</h2><p className="text-xs text-slate-500 mt-1">{json.report_type || '—'} · schema {json.schema || '—'}</p></div><div className="flex gap-2"><button disabled={!markdown} onClick={() => { navigator.clipboard.writeText(markdown); setCopied(true); setTimeout(() => setCopied(false), 1500); }} className="px-3 py-2 rounded-lg bg-slate-800 disabled:opacity-40 text-xs flex items-center gap-1">{copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}复制 Markdown</button><button onClick={() => download('md')} disabled={!markdown} className="px-3 py-2 rounded-lg bg-cyan-600 disabled:opacity-40 text-xs flex items-center gap-1"><Download className="w-3 h-3" />MD</button><button onClick={() => download('json')} className="px-3 py-2 rounded-lg bg-cyan-600 text-xs flex items-center gap-1"><Download className="w-3 h-3" />JSON</button></div></div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">{Object.entries(json.summary || {}).slice(0, 16).map(([key, value]) => <div key={key} className="p-3 rounded-xl bg-slate-900 border border-slate-800"><div className="text-[10px] text-slate-500">{key}</div><div className="text-sm font-mono font-bold mt-1">{String(value)}</div></div>)}</div>
      {markdown ? <pre className="p-5 rounded-2xl bg-slate-950 border border-slate-800 text-xs text-slate-300 whitespace-pre-wrap overflow-auto max-h-[60vh]">{markdown}</pre> : <pre className="p-5 rounded-2xl bg-slate-950 border border-slate-800 text-xs text-slate-300 whitespace-pre-wrap overflow-auto max-h-[60vh]">{JSON.stringify(json, null, 2)}</pre>}
    </div>
  );
};
