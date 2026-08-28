import React, { useState } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Lock,
  Key,
  FileCode,
  Terminal,
  FileText,
  Copy,
  Check,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Search,
  Sparkles,
  ShieldCheck,
  Eye,
  Database,
  Hash,
} from 'lucide-react';
import { Finding, EvidenceItem, SeverityLevel } from '../../types';

interface FindingsEvidenceTabProps {
  findings: Finding[];
  highlightEvidenceId?: string | null;
  onTraceInExecution?: (findingId: string) => void;
}

export const FindingsEvidenceTab: React.FC<FindingsEvidenceTabProps> = ({
  findings,
  highlightEvidenceId,
  onTraceInExecution,
}) => {
  const [selectedFindingId, setSelectedFindingId] = useState<string>(
    findings[0]?.id || ''
  );
  const [activeEvidenceTab, setActiveEvidenceTab] = useState<'all' | 'credentials' | 'files' | 'pocs'>('all');
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const selectedFinding =
    findings.find((f) => f.id === selectedFindingId) || findings[0];

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const getSeverityBadge = (sev: SeverityLevel) => {
    switch (sev) {
      case 'CRITICAL':
        return (
          <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse" />
            严重 (CRITICAL)
          </span>
        );
      case 'HIGH':
        return (
          <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
            高危 (HIGH)
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/40">
            中危 (MEDIUM)
          </span>
        );
      default:
        return (
          <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-slate-500/20 text-slate-300 border border-slate-500/40">
            {sev}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-10">
      {/* Top Banner: 结论优先理念 */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white">
                发现与证据中心 (Findings & Evidence Locker)
              </h2>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                100% 事实验证
              </span>
            </div>
            <p className="text-xs text-slate-400">
              结论先行 · 二次验证排除误报 · 关键凭据与战果证据全量上锁留痕
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 font-mono">
            已确认发现: <strong className="text-rose-400">{findings.length}</strong> 项
          </span>
        </div>
      </div>

      {/* Main Grid: Left Column Findings List (Conclusion-First) / Right Column Details (Verification + Evidence Locker) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left 5 Cols: Findings Summary List (结论列表) */}
        <div className="lg:col-span-5 space-y-3">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider px-1 flex items-center justify-between">
            <span>战果与风险结论列表</span>
            <span className="text-[11px] font-mono text-slate-500">点击查看详情</span>
          </div>

          <div className="space-y-2.5">
            {findings.map((f) => {
              const isSelected = selectedFindingId === f.id;
              const isCritical = f.severity === 'CRITICAL';

              return (
                <div
                  key={f.id}
                  onClick={() => setSelectedFindingId(f.id)}
                  className={`p-4 rounded-xl border transition-all duration-150 cursor-pointer select-none relative ${
                    isSelected
                      ? 'bg-slate-900 border-cyan-400 ring-2 ring-cyan-500/20 shadow-lg shadow-cyan-950/30'
                      : isCritical
                      ? 'bg-slate-900/80 border-rose-500/40 hover:border-rose-400'
                      : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    {getSeverityBadge(f.severity)}

                    <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> 已确认
                    </span>
                  </div>

                  <h3
                    className={`text-sm font-bold leading-snug mb-1.5 ${
                      isSelected ? 'text-white' : 'text-slate-200'
                    }`}
                  >
                    {f.title}
                  </h3>

                  <div className="text-xs text-slate-400 font-mono mb-2 flex items-center gap-2">
                    <span>影响资产:</span>
                    <span className="text-cyan-300 font-semibold truncate">
                      {f.affectedAsset}
                    </span>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 font-mono">
                    <span>{f.cve || '通用高危'}</span>
                    <span className="text-purple-300 flex items-center gap-1">
                      <Lock className="w-3 h-3" />
                      {f.evidenceList.length} 份到手证据
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right 7 Cols: Expanded Detail Panel (事实验证 + 证据保险箱) */}
        <div className="lg:col-span-7 space-y-4">
          {selectedFinding ? (
            <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-5">
              {/* Header Title & Target */}
              <div className="border-b border-slate-800 pb-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {getSeverityBadge(selectedFinding.severity)}
                    {selectedFinding.cve && (
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-bold">
                        {selectedFinding.cve}
                      </span>
                    )}
                    {selectedFinding.cvss && (
                      <span className="text-xs font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20 font-bold">
                        CVSS {selectedFinding.cvss}
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-slate-500 font-mono">
                    发现时间: {selectedFinding.discoveryTime}
                  </span>
                </div>

                <h2 className="text-base font-bold text-white leading-relaxed">
                  {selectedFinding.title}
                </h2>
                <div className="text-xs text-slate-400 font-mono mt-1">
                  目标位置: <span className="text-cyan-300">{selectedFinding.affectedUrl}</span>
                </div>
              </div>

              {/* 1. 重点模块：事实验证过程 (Fact Verification - 排除自嗨与误报) */}
              <div className="bg-slate-950/80 border border-emerald-500/30 rounded-xl p-4 relative overflow-hidden">
                <div className="flex items-center justify-between mb-2.5">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-bold text-emerald-300 tracking-wide">
                      事实验证与抗幻觉校验记录 (Fact Verification)
                    </span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold">
                    复现成功率 100%
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-300">
                    <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                      <span className="text-[10px] text-slate-400 block mb-0.5">验证方式</span>
                      <span className="font-medium text-slate-200">
                        {selectedFinding.verification.method}
                      </span>
                    </div>
                    <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                      <span className="text-[10px] text-slate-400 block mb-0.5">验证节点</span>
                      <span className="font-mono text-purple-300">
                        {selectedFinding.verification.verifierWorker}
                      </span>
                    </div>
                  </div>

                  <div className="p-2.5 rounded bg-slate-900/90 border border-emerald-500/20 text-slate-300 text-xs leading-relaxed">
                    <span className="text-emerald-400 font-semibold block mb-0.5">
                      ✓ 防误报校验结论：
                    </span>
                    {selectedFinding.verification.antiHallucinationCheck}
                  </div>
                </div>
              </div>

              {/* 2. 重点模块：证据保险箱 (Evidence Locker - 凭证、截图、文件、PoC) */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Lock className="w-4 h-4 text-purple-400" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                      证据保险箱 (Evidence Locker · 证据到手)
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono text-purple-300 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                    共 {selectedFinding.evidenceList.length} 项硬核证据
                  </span>
                </div>

                {/* Evidence Cards Stack */}
                <div className="space-y-3">
                  {selectedFinding.evidenceList.map((ev) => (
                    <div
                      key={ev.id}
                      className="bg-slate-950 rounded-xl border border-slate-800 overflow-hidden shadow-inner"
                    >
                      {/* Evidence Header */}
                      <div className="p-3 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {ev.type === 'credential' ? (
                            <Key className="w-3.5 h-3.5 text-amber-400" />
                          ) : ev.type === 'file' ? (
                            <FileText className="w-3.5 h-3.5 text-cyan-400" />
                          ) : ev.type === 'poc' ? (
                            <FileCode className="w-3.5 h-3.5 text-rose-400" />
                          ) : (
                            <Terminal className="w-3.5 h-3.5 text-emerald-400" />
                          )}
                          <span className="text-xs font-bold text-slate-200">
                            {ev.title}
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleCopy(ev.content, ev.id)}
                            className="text-[11px] text-slate-400 hover:text-white flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 transition-colors"
                          >
                            {copiedText === ev.id ? (
                              <>
                                <Check className="w-3 h-3 text-emerald-400" /> 已复制
                              </>
                            ) : (
                              <>
                                <Copy className="w-3 h-3" /> 复制证据
                              </>
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Evidence Content */}
                      <pre className="p-3 text-xs font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-56">
                        {ev.content}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>

              {/* 3. PoC 命令与修复建议 */}
              <div className="space-y-3 pt-2 border-t border-slate-800">
                <div>
                  <span className="text-xs font-bold text-slate-400 block mb-1">
                    独立复现 PoC 命令：
                  </span>
                  <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between text-xs font-mono text-cyan-300">
                    <span className="truncate mr-2">{selectedFinding.pocCommand}</span>
                    <button
                      onClick={() => handleCopy(selectedFinding.pocCommand, 'poc-cmd')}
                      className="text-slate-400 hover:text-white shrink-0"
                    >
                      {copiedText === 'poc-cmd' ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                <div>
                  <span className="text-xs font-bold text-slate-400 block mb-1">
                    应急修复加固建议：
                  </span>
                  <p className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 text-xs text-slate-300 leading-relaxed">
                    {selectedFinding.remediation}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-12 text-center text-slate-500">
              请选择左侧漏洞项以查看事实验证与证据保险箱
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
