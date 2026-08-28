import React, { useState } from 'react';
import {
  Terminal,
  Clock,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Search,
  ExternalLink,
  ShieldCheck,
  Server,
  Zap,
  Copy,
  Check,
  ShieldAlert,
  ArrowRight,
  Globe,
  Cpu,
  Layers,
  Filter,
  Sparkles,
  RefreshCw,
  Sliders,
  CheckCheck,
} from 'lucide-react';
import { ExecutionEvent, Finding } from '../../types';

interface ExecutionTabProps {
  events: ExecutionEvent[];
  findings?: Finding[];
  initialTraceFindingId?: string | null;
  initialSelectedFindingId?: string | null;
  onViewEvidence?: (evidenceId: string) => void;
}

export const ExecutionTab: React.FC<ExecutionTabProps> = ({
  events,
  findings = [],
  initialTraceFindingId = null,
  initialSelectedFindingId = null,
  onViewEvidence,
}) => {
  // Selected finding for verification trace
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(
    initialTraceFindingId || initialSelectedFindingId
  );

  React.useEffect(() => {
    if (initialTraceFindingId || initialSelectedFindingId) {
      setSelectedFindingId(initialTraceFindingId || initialSelectedFindingId);
    }
  }, [initialTraceFindingId, initialSelectedFindingId]);

  const [expandedId, setExpandedId] = useState<string | null>(
    events[events.length - 1]?.id || null
  );
  const [searchFilter, setSearchFilter] = useState('');
  const [traceFilterType, setTraceFilterType] = useState<
    'all' | 'initial_discovery' | 'ai_secondary_verification'
  >('all');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [activeDetailTab, setActiveDetailTab] = useState<
    Record<string, 'console' | 'network' | 'worker'>
  >({});

  // Filter events according to selected finding trace and search
  const filteredEvents = events.filter((e) => {
    // If a finding is selected for trace
    if (selectedFindingId) {
      const matchFinding =
        e.findingId === selectedFindingId ||
        (e.findingIds && e.findingIds.includes(selectedFindingId));
      if (!matchFinding) return false;
    }

    // Trace type filter pill
    if (traceFilterType !== 'all') {
      if (e.traceType !== traceFilterType) return false;
    }

    // Search query filter
    if (searchFilter.trim()) {
      const q = searchFilter.toLowerCase();
      return (
        e.title.toLowerCase().includes(q) ||
        e.tool.toLowerCase().includes(q) ||
        e.target.toLowerCase().includes(q) ||
        (e.outputSummary && e.outputSummary.toLowerCase().includes(q)) ||
        (e.rawOutput && e.rawOutput.toLowerCase().includes(q)) ||
        (e.networkTrace?.url && e.networkTrace.url.toLowerCase().includes(q)) ||
        (e.workerTrace?.command && e.workerTrace.command.toLowerCase().includes(q))
      );
    }

    return true;
  });

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getActiveTabForEvent = (id: string) => {
    return activeDetailTab[id] || 'console';
  };

  const setActiveTabForEvent = (
    id: string,
    tab: 'console' | 'network' | 'worker'
  ) => {
    setActiveDetailTab((prev) => ({ ...prev, [id]: tab }));
  };

  // Find the active selected finding object
  const currentTraceFinding = findings.find((f) => f.id === selectedFindingId);

  // Group events related to the current trace finding
  const traceEvents = selectedFindingId
    ? events.filter(
        (e) =>
          e.findingId === selectedFindingId ||
          (e.findingIds && e.findingIds.includes(selectedFindingId))
      )
    : [];

  const initialDiscoveryCount = traceEvents.filter(
    (e) => e.traceType === 'initial_discovery'
  ).length;
  const secondaryVerifyCount = traceEvents.filter(
    (e) => e.traceType === 'ai_secondary_verification'
  ).length;

  return (
    <div className="space-y-5 max-w-6xl mx-auto pb-10">
      {/* 1. 【验证逻辑溯源】选择与控制中心 (Traceability Control Bar) */}
      <div className="bg-slate-900/95 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800/80 pb-3.5">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/30 border border-cyan-500/30 text-cyan-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-white tracking-wide">
                  验证逻辑溯源 (Trace Verification Logic)
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-semibold">
                  全流程确证链条
                </span>
              </div>
              <p className="text-xs text-slate-400">
                点击下方漏洞条目，高亮追踪“初步扫描发现”与“AI二次验证确认”的请求回显与 Worker 容器沙箱日志
              </p>
            </div>
          </div>

          {/* Color Code Legend */}
          <div className="flex items-center gap-2 text-xs font-mono shrink-0 bg-slate-950/70 p-2 rounded-xl border border-slate-800">
            <span className="text-slate-400 text-[11px] mr-1">色彩编码:</span>
            <span className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center gap-1.5 font-semibold text-[11px]">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              初步扫描发现 (Recon)
            </span>
            <span className="px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 flex items-center gap-1.5 font-semibold text-[11px]">
              <span className="w-2 h-2 rounded-full bg-cyan-400" />
              AI 二次验证确认 (Verified)
            </span>
          </div>
        </div>

        {/* Finding Selector Pills */}
        <div className="space-y-2">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>选择溯源漏洞靶标：</span>
            {selectedFindingId && (
              <button
                onClick={() => {
                  setSelectedFindingId(null);
                  setTraceFilterType('all');
                }}
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-mono transition-colors"
              >
                <RefreshCw className="w-3 h-3" /> 重置为全量执行流
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
            {/* All Events Button */}
            <button
              id="trace-all-events"
              onClick={() => {
                setSelectedFindingId(null);
                setTraceFilterType('all');
              }}
              className={`p-3 rounded-xl border text-left transition-all duration-150 relative ${
                selectedFindingId === null
                  ? 'bg-slate-800 border-cyan-400/80 ring-2 ring-cyan-500/20 text-white shadow-lg shadow-cyan-950/20'
                  : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-900 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold truncate">全部执行流</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                  {events.length} 条
                </span>
              </div>
              <p className="text-[11px] text-slate-400 truncate">
                展示任务全生命周期的时序 Session 记录
              </p>
            </button>

            {/* Finding Trace Cards */}
            {findings.map((f) => {
              const isSelected = selectedFindingId === f.id;
              const relatedEvts = events.filter(
                (e) =>
                  e.findingId === f.id ||
                  (e.findingIds && e.findingIds.includes(f.id))
              );
              const discCount = relatedEvts.filter(
                (e) => e.traceType === 'initial_discovery'
              ).length;
              const verCount = relatedEvts.filter(
                (e) => e.traceType === 'ai_secondary_verification'
              ).length;

              return (
                <button
                  key={f.id}
                  id={`trace-finding-${f.id}`}
                  onClick={() => {
                    setSelectedFindingId(f.id);
                    setTraceFilterType('all');
                    // Automatically expand the first related event
                    if (relatedEvts.length > 0) {
                      setExpandedId(relatedEvts[0].id);
                    }
                  }}
                  className={`p-3 rounded-xl border text-left transition-all duration-150 relative group ${
                    isSelected
                      ? 'bg-slate-900 border-cyan-400 ring-2 ring-cyan-500/20 shadow-xl shadow-cyan-950/40'
                      : f.severity === 'CRITICAL'
                      ? 'bg-slate-950/80 border-rose-500/30 hover:border-rose-400/60'
                      : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span
                      className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                        f.severity === 'CRITICAL'
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      }`}
                    >
                      {f.cve || f.severity}
                    </span>
                    <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
                      <CheckCheck className="w-3 h-3" /> 已确证
                    </span>
                  </div>

                  <h3
                    className={`text-xs font-bold line-clamp-1 mb-1 ${
                      isSelected ? 'text-cyan-300' : 'text-slate-200'
                    }`}
                  >
                    {f.title}
                  </h3>

                  <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
                    <span className="text-amber-400/90 font-semibold">
                      扫描:{discCount}
                    </span>
                    <span>·</span>
                    <span className="text-cyan-400/90 font-semibold">
                      确证:{verCount}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Active Trace Summary Banner if a finding is selected */}
        {currentTraceFinding && (
          <div className="p-3.5 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 border border-cyan-500/40 rounded-xl space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
                <span className="text-xs font-bold text-white">
                  当前溯源靶标：
                  <strong className="text-cyan-300 ml-1">
                    {currentTraceFinding.title}
                  </strong>
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  ({currentTraceFinding.affectedUrl})
                </span>
              </div>

              {/* Sub filter by trace type */}
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-mono">
                <button
                  onClick={() => setTraceFilterType('all')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    traceFilterType === 'all'
                      ? 'bg-slate-800 text-white font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  全部轨迹 ({traceEvents.length})
                </button>
                <button
                  onClick={() => setTraceFilterType('initial_discovery')}
                  className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1 ${
                    traceFilterType === 'initial_discovery'
                      ? 'bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/30'
                      : 'text-amber-400/80 hover:text-amber-300'
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  初步扫描 ({initialDiscoveryCount})
                </button>
                <button
                  onClick={() => setTraceFilterType('ai_secondary_verification')}
                  className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1 ${
                    traceFilterType === 'ai_secondary_verification'
                      ? 'bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/30'
                      : 'text-cyan-400/80 hover:text-cyan-300'
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  AI 二次确证 ({secondaryVerifyCount})
                </button>
              </div>
            </div>

            {/* Visual Process Flow Diagram */}
            <div className="p-2.5 bg-slate-950/80 rounded-lg border border-slate-800 text-xs flex flex-col md:flex-row items-center justify-between gap-3 text-slate-300">
              <div className="flex items-center gap-2 text-[11px] font-mono text-amber-300">
                <span className="w-5 h-5 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center font-bold">
                  1
                </span>
                <span>特征扫描命中</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-600 hidden md:block" />

              <div className="flex items-center gap-2 text-[11px] font-mono text-purple-300">
                <span className="w-5 h-5 rounded-full bg-purple-500/20 border border-purple-500/40 flex items-center justify-center font-bold">
                  2
                </span>
                <span>AI 决策构造无害 PoC</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-600 hidden md:block" />

              <div className="flex items-center gap-2 text-[11px] font-mono text-cyan-300">
                <span className="w-5 h-5 rounded-full bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center font-bold">
                  3
                </span>
                <span>动态沙箱执行确证</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-600 hidden md:block" />

              <div className="flex items-center gap-2 text-[11px] font-mono text-emerald-300">
                <span className="w-5 h-5 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center font-bold">
                  4
                </span>
                <span>防误报校验 & 证据入库</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 2. Session Header Toolbar (Search & Filter Status) */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900/90 border border-slate-800 rounded-xl p-3.5">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Terminal className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-bold text-white">
            {selectedFindingId ? '漏洞溯源执行时序流' : '执行过程 (Session 流)'}
          </h3>
          <span className="text-xs text-slate-400 font-mono">
            共 {filteredEvents.length} 条时序记录
            {selectedFindingId && ' (已过滤高亮关联事件)'}
          </span>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative w-full sm:w-72">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="搜索请求 URL、命令或断言..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            />
          </div>
        </div>
      </div>

      {/* 3. Streamlined & Color-Coded Session Event List */}
      <div className="space-y-3">
        {filteredEvents.length === 0 ? (
          <div className="p-12 text-center bg-slate-900/50 border border-slate-800 rounded-xl text-slate-400 text-xs">
            未检索到匹配的执行事件或溯源日志记录
          </div>
        ) : (
          filteredEvents.map((evt) => {
            const isExpanded = expandedId === evt.id;
            const isRunning = evt.status === 'running';
            const isInitialDiscovery = evt.traceType === 'initial_discovery';
            const isSecondaryVerification =
              evt.traceType === 'ai_secondary_verification';
            const currentSubTab = getActiveTabForEvent(evt.id);

            // Determine border and accent styling based on traceType color coding
            let cardStyle =
              'bg-slate-900/60 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900/80';
            if (isExpanded) {
              if (isSecondaryVerification) {
                cardStyle =
                  'bg-slate-900 border-cyan-500/60 ring-1 ring-cyan-500/30 shadow-xl shadow-cyan-950/30';
              } else if (isInitialDiscovery) {
                cardStyle =
                  'bg-slate-900 border-amber-500/60 ring-1 ring-amber-500/30 shadow-xl shadow-amber-950/30';
              } else {
                cardStyle =
                  'bg-slate-900 border-cyan-500/40 shadow-lg shadow-cyan-950/20';
              }
            } else if (isSecondaryVerification) {
              cardStyle =
                'bg-slate-900/80 border-cyan-500/30 hover:border-cyan-400/60';
            } else if (isInitialDiscovery) {
              cardStyle =
                'bg-slate-900/80 border-amber-500/30 hover:border-amber-400/60';
            }

            return (
              <div
                key={evt.id}
                id={`event-card-${evt.id}`}
                className={`border rounded-xl transition-all duration-150 overflow-hidden ${cardStyle}`}
              >
                {/* Row Header - Streamlined with Trace Badge */}
                <div
                  onClick={() => toggleExpand(evt.id)}
                  className="px-4 py-3 flex items-center justify-between cursor-pointer select-none"
                >
                  <div className="flex items-center gap-2.5 sm:gap-3 min-w-0 flex-wrap sm:flex-nowrap">
                    <button className="text-slate-400 hover:text-slate-200 shrink-0">
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-cyan-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4" />
                      )}
                    </button>

                    <span className="text-xs font-mono text-cyan-400 font-semibold shrink-0">
                      {evt.timeDisplay}
                    </span>

                    {/* Trace Type Color-Coded Badge */}
                    {isInitialDiscovery && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold shrink-0 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                        初步扫描发现
                      </span>
                    )}

                    {isSecondaryVerification && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 font-bold shrink-0 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                        AI 二次验证确认
                      </span>
                    )}

                    <span className="text-sm font-medium text-slate-100 truncate">
                      {evt.title}
                    </span>

                    {evt.evidenceId && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/25 shrink-0 hidden md:inline">
                        证据 {evt.evidenceId}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-3 shrink-0 ml-2">
                    <span className="text-xs text-slate-400 font-mono hidden md:inline">
                      {evt.tool}
                    </span>

                    <div className="flex items-center gap-1.5">
                      {isRunning ? (
                        <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-ping" />
                          执行中
                        </span>
                      ) : evt.status === 'completed' ? (
                        <span className="text-xs font-mono text-emerald-400 flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          完成
                        </span>
                      ) : (
                        <span className="text-xs font-mono text-rose-400 flex items-center gap-1">
                          <AlertCircle className="w-3.5 h-3.5" />
                          失败
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Unfolded Detailed View with Tab Switcher for Console / Network / Worker */}
                {isExpanded && (
                  <div className="px-5 pb-5 pt-3 border-t border-slate-800/80 space-y-4 bg-slate-950/60">
                    {/* Metadata Specs Bar */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-slate-900/80 p-3 rounded-lg border border-slate-800">
                      <div>
                        <span className="text-slate-400 block text-[11px]">使用工具</span>
                        <span className="font-mono text-slate-200 font-medium">
                          {evt.tool}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[11px]">目标资产</span>
                        <span className="font-mono text-cyan-300 font-medium truncate block">
                          {evt.target}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[11px]">执行耗时</span>
                        <span className="font-mono text-slate-200">{evt.duration}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[11px]">分配 Worker</span>
                        <span className="font-mono text-purple-300">
                          {evt.workerNode || evt.workerTrace?.workerId || 'Worker-01'}
                        </span>
                      </div>
                    </div>

                    {/* Output Summary */}
                    <div>
                      <span className="text-xs font-semibold text-slate-300 block mb-1">
                        输出摘要：
                      </span>
                      <p className="text-xs text-slate-300 bg-slate-900/70 p-2.5 rounded-lg border border-slate-800/80 leading-relaxed">
                        {evt.outputSummary}
                      </p>
                    </div>

                    {/* Sub Tab Navigation inside Event: [控制台回显] | [网络请求与响应] | [Worker 执行轨迹] */}
                    <div className="flex items-center gap-1 border-b border-slate-800 pb-2">
                      <button
                        onClick={() => setActiveTabForEvent(evt.id, 'console')}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                          currentSubTab === 'console'
                            ? 'bg-slate-800 text-white border border-slate-700'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                        }`}
                      >
                        <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                        控制台原始回显
                      </button>

                      {evt.networkTrace && (
                        <button
                          onClick={() => setActiveTabForEvent(evt.id, 'network')}
                          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                            currentSubTab === 'network'
                              ? isInitialDiscovery
                                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                          }`}
                        >
                          <Globe className="w-3.5 h-3.5 text-cyan-400" />
                          网络请求与响应溯源
                          <span className="text-[10px] font-mono px-1 rounded bg-slate-800 text-slate-300">
                            {evt.networkTrace.method}
                          </span>
                        </button>
                      )}

                      {evt.workerTrace && (
                        <button
                          onClick={() => setActiveTabForEvent(evt.id, 'worker')}
                          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                            currentSubTab === 'worker'
                              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                          }`}
                        >
                          <Cpu className="w-3.5 h-3.5 text-purple-400" />
                          Worker 容器沙箱日志
                          <span className="text-[10px] font-mono px-1 rounded bg-slate-800 text-emerald-400">
                            Code 0
                          </span>
                        </button>
                      )}
                    </div>

                    {/* Content View 1: Console Raw Output */}
                    {currentSubTab === 'console' && (
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                            CLI 终端输出：
                          </span>
                          <button
                            onClick={() => handleCopy(evt.rawOutput, `${evt.id}-raw`)}
                            className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1"
                          >
                            {copiedId === `${evt.id}-raw` ? (
                              <>
                                <Check className="w-3 h-3 text-emerald-400" /> 已复制
                              </>
                            ) : (
                              <>
                                <Copy className="w-3 h-3" /> 复制回显
                              </>
                            )}
                          </button>
                        </div>

                        <pre className="p-3.5 bg-slate-950 rounded-lg border border-slate-800 text-slate-300 text-xs font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed shadow-inner max-h-72">
                          {evt.rawOutput}
                        </pre>
                      </div>
                    )}

                    {/* Content View 2: Network Request & Response Trace */}
                    {currentSubTab === 'network' && evt.networkTrace && (
                      <div className="space-y-3">
                        {/* Request Header Bar */}
                        <div className="p-3 bg-slate-900/90 rounded-lg border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                          <div className="flex items-center gap-2 overflow-hidden">
                            <span
                              className={`px-2 py-0.5 rounded font-mono font-bold text-xs ${
                                evt.networkTrace.method === 'POST'
                                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                                  : evt.networkTrace.method === 'GET'
                                  ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                                  : 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                              }`}
                            >
                              {evt.networkTrace.method}
                            </span>
                            <span className="font-mono text-cyan-300 font-semibold truncate">
                              {evt.networkTrace.url}
                            </span>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            {evt.networkTrace.responseCode && (
                              <span
                                className={`text-xs font-mono px-2 py-0.5 rounded font-bold ${
                                  evt.networkTrace.responseCode >= 200 &&
                                  evt.networkTrace.responseCode < 300
                                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                    : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                }`}
                              >
                                Status: {evt.networkTrace.responseCode}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Assertion Match Rule Highlighting */}
                        {evt.networkTrace.assertionMatch && (
                          <div
                            className={`p-3 rounded-lg border text-xs ${
                              isSecondaryVerification
                                ? 'bg-cyan-950/30 border-cyan-500/40 text-cyan-200'
                                : 'bg-amber-950/30 border-amber-500/40 text-amber-200'
                            }`}
                          >
                            <span className="font-bold block mb-1 flex items-center gap-1.5">
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                              命中验证断言 (Assertion Match)：
                            </span>
                            <code className="font-mono text-[11px] block bg-slate-950/80 p-2 rounded border border-slate-800 text-slate-200">
                              {evt.networkTrace.assertionMatch}
                            </code>
                          </div>
                        )}

                        {/* Request & Response Split Grid */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 text-xs">
                          {/* Request Box */}
                          <div className="space-y-1.5">
                            <div className="flex items-center justify-between text-slate-400 text-[11px] font-semibold">
                              <span>HTTP 请求报文 (Request)</span>
                              <button
                                onClick={() =>
                                  handleCopy(
                                    JSON.stringify(evt.networkTrace?.headers, null, 2) +
                                      '\n\n' +
                                      (evt.networkTrace?.requestBody || ''),
                                    `${evt.id}-req`
                                  )
                                }
                                className="hover:text-slate-200 flex items-center gap-1"
                              >
                                {copiedId === `${evt.id}-req` ? '已复制' : '复制请求'}
                              </button>
                            </div>
                            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono text-[11px] text-slate-300 max-h-56 overflow-y-auto space-y-2">
                              {evt.networkTrace.headers && (
                                <div className="text-slate-400 pb-2 border-b border-slate-800/80">
                                  {Object.entries(evt.networkTrace.headers).map(
                                    ([k, v]) => (
                                      <div key={k} className="truncate">
                                        <span className="text-cyan-400">{k}:</span>{' '}
                                        {v}
                                      </div>
                                    )
                                  )}
                                </div>
                              )}
                              {evt.networkTrace.requestBody ? (
                                <pre className="text-emerald-300 whitespace-pre-wrap">
                                  {evt.networkTrace.requestBody}
                                </pre>
                              ) : (
                                <span className="text-slate-600 italic">
                                  (无请求体 Payload)
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Response Box */}
                          <div className="space-y-1.5">
                            <div className="flex items-center justify-between text-slate-400 text-[11px] font-semibold">
                              <span>HTTP 响应报文 (Response)</span>
                              <button
                                onClick={() =>
                                  handleCopy(
                                    evt.networkTrace?.responseBody || '',
                                    `${evt.id}-resp`
                                  )
                                }
                                className="hover:text-slate-200 flex items-center gap-1"
                              >
                                {copiedId === `${evt.id}-resp` ? '已复制' : '复制响应'}
                              </button>
                            </div>
                            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono text-[11px] text-slate-300 max-h-56 overflow-y-auto space-y-2">
                              {evt.networkTrace.responseHeaders && (
                                <div className="text-slate-400 pb-2 border-b border-slate-800/80">
                                  {Object.entries(evt.networkTrace.responseHeaders).map(
                                    ([k, v]) => (
                                      <div key={k} className="truncate">
                                        <span className="text-purple-400">{k}:</span>{' '}
                                        {v}
                                      </div>
                                    )
                                  )}
                                </div>
                              )}
                              <pre className="text-cyan-200 whitespace-pre-wrap">
                                {evt.networkTrace.responseBody || '(空响应体)'}
                              </pre>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Content View 3: Worker Sandbox Execution Log */}
                    {currentSubTab === 'worker' && evt.workerTrace && (
                      <div className="space-y-3">
                        <div className="p-3.5 bg-slate-900/90 rounded-lg border border-slate-800 space-y-3 text-xs">
                          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2.5">
                            <div className="flex items-center gap-2">
                              <Server className="w-4 h-4 text-purple-400" />
                              <span className="font-bold text-white">
                                {evt.workerTrace.workerId}
                              </span>
                              {evt.workerTrace.containerSandbox && (
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                                  沙箱: {evt.workerTrace.containerSandbox}
                                </span>
                              )}
                            </div>

                            <div className="flex items-center gap-3 font-mono text-[11px]">
                              <span className="text-slate-400">
                                退出码: <strong className="text-emerald-400">0 (OK)</strong>
                              </span>
                              <span className="text-slate-400">
                                耗时:{' '}
                                <strong className="text-slate-200">
                                  {evt.workerTrace.executionTimeMs} ms
                                </strong>
                              </span>
                              {evt.workerTrace.memoryDelta && (
                                <span className="text-slate-400">
                                  内存增量:{' '}
                                  <strong className="text-slate-200">
                                    {evt.workerTrace.memoryDelta}
                                  </strong>
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Verification Logic Summary */}
                          {evt.workerTrace.verificationLogicSummary && (
                            <div className="p-2.5 rounded bg-slate-950 border border-purple-500/20 text-slate-300 leading-relaxed">
                              <span className="text-purple-400 font-semibold block mb-0.5">
                                AI 验证逻辑判定：
                              </span>
                              {evt.workerTrace.verificationLogicSummary}
                            </div>
                          )}

                          {/* Shell Command Executed */}
                          <div>
                            <div className="flex items-center justify-between text-slate-400 text-[11px] mb-1">
                              <span>Worker 执行命令指令 (Command Line)：</span>
                              <button
                                onClick={() =>
                                  handleCopy(evt.workerTrace?.command || '', `${evt.id}-cmd`)
                                }
                                className="hover:text-slate-200 flex items-center gap-1"
                              >
                                {copiedId === `${evt.id}-cmd` ? '已复制' : '复制命令'}
                              </button>
                            </div>
                            <pre className="p-3 bg-slate-950 rounded border border-slate-800 text-cyan-300 font-mono text-[11px] overflow-x-auto">
                              $ {evt.workerTrace.command}
                            </pre>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Evidence Link Footer */}
                    {evt.evidenceId && (
                      <div className="pt-2 flex items-center justify-between text-xs border-t border-slate-800/80">
                        <span className="text-slate-400">
                          该步骤已生成硬核证据快照 (ID: {evt.evidenceId})
                        </span>
                        <button
                          onClick={() => onViewEvidence?.(evt.evidenceId!)}
                          className="px-3 py-1 bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-lg font-medium transition-colors flex items-center gap-1.5"
                        >
                          <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
                          在证据保险箱中查看
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
