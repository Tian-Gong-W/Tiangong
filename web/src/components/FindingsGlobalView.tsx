import React, { useState } from 'react';
import {
  Search,
  ShieldAlert,
  CheckCircle2,
  Lock,
  ExternalLink,
  ChevronRight,
  Filter,
  Copy,
  Check,
  Terminal,
  FileText,
  Key,
} from 'lucide-react';
import { Finding, SeverityLevel } from '../types';

interface FindingsGlobalViewProps {
  findings: Finding[];
  onSelectFindingTask?: (taskId: string) => void;
}

export const FindingsGlobalView: React.FC<FindingsGlobalViewProps> = ({
  findings,
  onSelectFindingTask,
}) => {
  const [selectedSev, setSelectedSev] = useState<string>('all');
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [activeFinding, setActiveFinding] = useState<Finding | null>(findings[0] || null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const filteredFindings = findings.filter((f) => {
    const matchSev = selectedSev === 'all' ? true : f.severity === selectedSev;
    const matchSearch =
      f.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      f.affectedAsset.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (f.cve && f.cve.toLowerCase().includes(searchFilter.toLowerCase()));
    return matchSev && matchSearch;
  });

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-slate-950 text-slate-100 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            <h1 className="text-xl font-bold text-white tracking-wide">
              全域发现与战果池 (Global Findings)
            </h1>
          </div>
          <p className="text-xs text-slate-400">
            结论先行 · 汇聚所有已完成事实验证的漏洞与硬核证据保险箱
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="px-3 py-1.5 rounded-lg bg-rose-500/10 text-rose-300 border border-rose-500/20 font-bold">
            严重: {findings.filter((f) => f.severity === 'CRITICAL').length}
          </span>
          <span className="px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-300 border border-amber-500/20 font-bold">
            高危: {findings.filter((f) => f.severity === 'HIGH').length}
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900/90 border border-slate-800 rounded-xl p-3">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          {['all', 'CRITICAL', 'HIGH', 'MEDIUM'].map((sev) => (
            <button
              key={sev}
              onClick={() => setSelectedSev(sev)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                selectedSev === sev
                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30 font-bold'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {sev === 'all' ? '全部级别' : sev}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="搜索 CVE、漏洞名或目标..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
      </div>

      {/* Main Content Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left 5 Cols: Findings List */}
        <div className="lg:col-span-5 space-y-2.5">
          {filteredFindings.map((f) => {
            const isSelected = activeFinding?.id === f.id;
            return (
              <div
                key={f.id}
                onClick={() => setActiveFinding(f)}
                className={`p-4 rounded-xl border transition-all duration-150 cursor-pointer ${
                  isSelected
                    ? 'bg-slate-900 border-cyan-400 ring-2 ring-cyan-500/20 shadow-lg'
                    : 'bg-slate-900/70 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span
                    className={`text-xs font-bold px-2 py-0.5 rounded font-mono ${
                      f.severity === 'CRITICAL'
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        : f.severity === 'HIGH'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                    }`}
                  >
                    {f.severity}
                  </span>
                  <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> 已确认
                  </span>
                </div>

                <h3 className="text-sm font-bold text-white mb-1 leading-snug">
                  {f.title}
                </h3>
                <div className="text-xs text-slate-400 font-mono">
                  目标: <span className="text-cyan-300">{f.affectedAsset}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Right 7 Cols: Expanded Detail Panel */}
        <div className="lg:col-span-7">
          {activeFinding ? (
            <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-5 shadow-xl">
              <div className="border-b border-slate-800 pb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 font-mono">
                    {activeFinding.severity} · {activeFinding.cve || '通用高危'}
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    所属任务: {activeFinding.taskName}
                  </span>
                </div>

                <h2 className="text-base font-bold text-white leading-relaxed">
                  {activeFinding.title}
                </h2>
                <div className="text-xs text-cyan-300 font-mono mt-1">
                  {activeFinding.affectedUrl}
                </div>
              </div>

              {/* Fact Verification */}
              <div className="p-4 rounded-xl bg-slate-950/90 border border-emerald-500/30 text-xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-emerald-400 font-bold flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4" />
                    事实验证记录 (Fact Verification)
                  </span>
                  <span className="text-emerald-300 font-mono text-[10px]">
                    置信度 100%
                  </span>
                </div>
                <p className="text-slate-300 leading-relaxed">
                  {activeFinding.verification.antiHallucinationCheck}
                </p>
                <div className="text-[11px] text-slate-400 font-mono">
                  验证方法: {activeFinding.verification.method}
                </div>
              </div>

              {/* Evidence Locker */}
              <div className="space-y-2">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5 text-purple-400" />
                  证据保险箱 ({activeFinding.evidenceList.length} 份战果证据)
                </h3>

                <div className="space-y-2">
                  {activeFinding.evidenceList.map((ev) => (
                    <div
                      key={ev.id}
                      className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1.5"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-slate-200">{ev.title}</span>
                        <button
                          onClick={() => handleCopy(ev.content, ev.id)}
                          className="text-[10px] text-slate-400 hover:text-white flex items-center gap-1"
                        >
                          {copiedId === ev.id ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-400" /> 已复制
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" /> 复制
                            </>
                          )}
                        </button>
                      </div>
                      <pre className="text-[11px] font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap max-h-36">
                        {ev.content}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>

              {/* Remediation */}
              <div className="pt-2 border-t border-slate-800 text-xs">
                <span className="font-bold text-slate-400 block mb-1">加固建议：</span>
                <p className="text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                  {activeFinding.remediation}
                </p>
              </div>
            </div>
          ) : (
            <div className="p-12 text-center text-slate-500 border border-dashed border-slate-800 rounded-2xl">
              选择左侧发现项查看详细证据
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
