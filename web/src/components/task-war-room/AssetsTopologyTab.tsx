import React, { useState } from 'react';
import {
  Globe,
  Server,
  ShieldAlert,
  CheckCircle2,
  HelpCircle,
  Lock,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Layers,
  Search,
} from 'lucide-react';
import { AssetDomain, AssetHost, AssetService } from '../../types';

interface AssetsTopologyTabProps {
  assetTree: AssetDomain;
  onViewFinding?: (findingId: string) => void;
}

export const AssetsTopologyTab: React.FC<AssetsTopologyTabProps> = ({
  assetTree,
  onViewFinding,
}) => {
  const [expandedHosts, setExpandedHosts] = useState<Record<string, boolean>>({
    '192.168.100.15': true,
    '192.168.100.254': true,
    '192.168.100.99': true,
    '192.168.100.88': false,
  });
  const [filterText, setFilterText] = useState('');

  const toggleHost = (ip: string) => {
    setExpandedHosts((prev) => ({ ...prev, [ip]: !prev[ip] }));
  };

  const getStatusBadge = (status: 'checked' | 'unchecked' | 'need_auth' | 'has_vuln') => {
    switch (status) {
      case 'has_vuln':
        return (
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 flex items-center gap-1 font-bold">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse" />
            有发现 (Vulnerable)
          </span>
        );
      case 'checked':
        return (
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            已检查
          </span>
        );
      case 'need_auth':
        return (
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1 font-semibold">
            <Lock className="w-3 h-3 text-amber-400" />
            需授权
          </span>
        );
      case 'unchecked':
      default:
        return (
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
            未检查
          </span>
        );
    }
  };

  const filteredHosts = (assetTree.hosts || []).filter(
    (h) =>
      h.ip.includes(filterText) ||
      (h.hostname && h.hostname.toLowerCase().includes(filterText.toLowerCase()))
  );

  return (
    <div className="space-y-5 max-w-6xl mx-auto pb-10">
      {/* Topology Header & Visual Legend */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white">
                资产树状覆盖图 (ARTEX 拓扑结构)
              </h2>
              <span className="text-xs font-mono text-cyan-300 px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20">
                {assetTree.domain}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              直观呈现「目标域名 → 主机 IP → 端口服务 → 关联漏洞」作战纵深
            </p>
          </div>
        </div>

        {/* 4 Clean Color Meaning Legends */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
            <span className="text-slate-300">已检查</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-500" />
            <span className="text-slate-400">未检查</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
            <span className="text-amber-300 font-medium">需授权</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
            <span className="text-rose-300 font-bold">有发现</span>
          </div>
        </div>
      </div>

      {/* Interactive Tree Container */}
      <div className="bg-slate-950/80 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        {/* Domain Root Node */}
        <div className="p-4 bg-slate-900 border border-cyan-500/40 rounded-xl flex items-center justify-between shadow-md">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <div className="text-sm font-bold text-white flex items-center gap-2">
                <span>{assetTree.domain}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  初始授权范围 (In Scope)
                </span>
              </div>
              <span className="text-xs text-slate-400 font-mono">
                已探测主机: {filteredHosts.length} 台 · 漏洞覆盖率 100%
              </span>
            </div>
          </div>

          <div className="text-right">
            <span className="text-xs font-mono text-cyan-300 font-semibold">
              Root Level
            </span>
          </div>
        </div>

        {/* Tree Branches (Hosts -> Services -> Vulns) */}
        <div className="pl-4 sm:pl-8 space-y-3 relative border-l-2 border-slate-800 ml-4 my-2">
          {filteredHosts.map((host) => {
            const isExpanded = expandedHosts[host.ip] ?? true;

            return (
              <div key={host.ip} className="relative group">
                {/* Horizontal branch line */}
                <div className="absolute -left-4 sm:-left-8 top-5 w-4 sm:w-8 h-0.5 bg-slate-800" />

                {/* Host Card */}
                <div
                  className={`p-3.5 rounded-xl border transition-all duration-150 ${
                    host.status === 'has_vuln'
                      ? 'bg-slate-900/90 border-rose-500/40 shadow-sm shadow-rose-950/20'
                      : host.status === 'need_auth'
                      ? 'bg-slate-900/80 border-amber-500/40'
                      : host.status === 'checked'
                      ? 'bg-slate-900/70 border-slate-800'
                      : 'bg-slate-900/40 border-slate-800/60 opacity-80'
                  }`}
                >
                  <div
                    onClick={() => toggleHost(host.ip)}
                    className="flex items-center justify-between cursor-pointer select-none"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <button className="text-slate-400 hover:text-white">
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-cyan-400" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                      </button>

                      <Server
                        className={`w-4 h-4 shrink-0 ${
                          host.status === 'has_vuln'
                            ? 'text-rose-400'
                            : host.status === 'need_auth'
                            ? 'text-amber-400'
                            : 'text-slate-400'
                        }`}
                      />

                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono font-bold text-slate-100">
                            {host.ip}
                          </span>
                          {host.hostname && (
                            <span className="text-xs text-slate-400 hidden sm:inline truncate">
                              ({host.hostname})
                            </span>
                          )}
                        </div>
                        {host.os && (
                          <span className="text-[11px] text-slate-400 font-mono block">
                            {host.os}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {getStatusBadge(host.status)}
                    </div>
                  </div>

                  {/* Sub-Branch: Services & Findings */}
                  {isExpanded && host.services && host.services.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-800/80 pl-6 space-y-2 relative border-l border-slate-800 ml-3">
                      {host.services.map((svc) => (
                        <div
                          key={`${host.ip}-${svc.port}`}
                          className={`p-2.5 rounded-lg border text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
                            svc.status === 'has_vuln'
                              ? 'bg-rose-950/20 border-rose-500/30'
                              : svc.status === 'need_auth'
                              ? 'bg-amber-950/20 border-amber-500/30'
                              : 'bg-slate-950/60 border-slate-800'
                          }`}
                        >
                          <div className="flex items-center gap-2.5">
                            <span className="font-mono font-bold text-cyan-300">
                              Port {svc.port}/{svc.protocol}
                            </span>
                            <span className="text-slate-300 font-semibold">
                              {svc.service}
                            </span>
                            {svc.version && (
                              <span className="text-[11px] text-slate-400 font-mono">
                                ({svc.version})
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-2">
                            {svc.findingIds && svc.findingIds.length > 0 ? (
                              <button
                                onClick={() => onViewFinding?.(svc.findingIds[0])}
                                className="px-2 py-0.5 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 text-[11px] font-bold transition-colors flex items-center gap-1"
                              >
                                <AlertTriangle className="w-3 h-3 text-rose-400" />
                                查看关联漏洞
                              </button>
                            ) : (
                              getStatusBadge(svc.status)
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
