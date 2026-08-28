import React, { useState } from 'react';
import {
  Globe,
  Server,
  Layers,
  Search,
  CheckCircle2,
  Lock,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Plus,
  Anchor,
  Database,
  Key,
  Network,
  Terminal,
  ExternalLink,
  Filter,
  Sparkles,
  Zap,
} from 'lucide-react';
import { Task } from '../types';
import { mockArtexAnchors } from '../data/mockData';

interface AssetsGlobalViewProps {
  tasks: Task[];
  onSelectTask?: (task: Task) => void;
  onOpenNewTaskModal?: () => void;
}

export const AssetsGlobalView: React.FC<AssetsGlobalViewProps> = ({
  tasks,
  onSelectTask,
  onOpenNewTaskModal,
}) => {
  const [activeTab, setActiveTab] = useState<'graph' | 'tree' | 'table'>('graph');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'has_vuln' | 'checked' | 'need_auth'>('all');
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>('host-192.168.100.15');

  // Compute aggregate stats across all tasks
  const allHosts = tasks.flatMap((t) => t.assetTree.hosts || []);
  const totalHosts = allHosts.length;
  const vulnHosts = allHosts.filter((h) => h.status === 'has_vuln').length;
  const checkedHosts = allHosts.filter((h) => h.status === 'checked').length;
  const needAuthHosts = allHosts.filter((h) => h.status === 'need_auth').length;
  const totalServices = allHosts.reduce((acc, h) => acc + (h.services?.length || 0), 0);

  const filteredHosts = allHosts.filter((h) => {
    const matchesSearch =
      h.ip.includes(searchQuery) ||
      (h.hostname && h.hostname.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus = statusFilter === 'all' || h.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="flex-1 p-5 md:p-8 overflow-y-auto bg-slate-950 text-slate-100 space-y-6 max-w-7xl mx-auto z-10 relative">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-bold">
              ARTEX DUAL-GRAPH
            </span>
            <span className="text-xs text-slate-400 font-mono">
              跨任务全局共享资产真值库 (Global Asset Truth Base)
            </span>
          </div>
          <h1 className="text-xl font-bold text-white tracking-wide flex items-center gap-2">
            全域资产真值图谱与双图锚点池
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            ARTEX 架构核心：全局资产真值库跨任务沉淀共享，多任务智能体自动继承历史探活与指纹结果
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={onOpenNewTaskModal}
            className="px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs transition-all flex items-center gap-1.5 cursor-pointer shadow-md"
          >
            <Plus className="w-3.5 h-3.5" />
            基于真值库发起专项渗透
          </button>
        </div>
      </div>

      {/* 4 Stats Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md">
          <div className="text-[11px] text-slate-400 font-semibold mb-1">全域根域名 & 资产段</div>
          <div className="text-xl font-bold text-white font-mono flex items-center gap-2">
            {tasks.length} <span className="text-xs font-normal text-slate-400">个域</span>
          </div>
          <div className="text-[10px] text-cyan-400 font-mono mt-1">覆盖率 100% (In-Scope)</div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md">
          <div className="text-[11px] text-slate-400 font-semibold mb-1">存活主机与容器实例</div>
          <div className="text-xl font-bold text-emerald-400 font-mono flex items-center gap-2">
            {totalHosts} <span className="text-xs font-normal text-slate-400">台</span>
          </div>
          <div className="text-[10px] text-emerald-400 font-mono mt-1">已确证 {checkedHosts} 台正常</div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md">
          <div className="text-[11px] text-slate-400 font-semibold mb-1">已突破 / 高危发现资产</div>
          <div className="text-xl font-bold text-rose-400 font-mono flex items-center gap-2">
            {vulnHosts} <span className="text-xs font-normal text-slate-400">处</span>
          </div>
          <div className="text-[10px] text-rose-400 font-mono mt-1">含 CVE-2022-22947 RCE</div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md">
          <div className="text-[11px] text-slate-400 font-semibold mb-1">ARTEX 动态双图锚点</div>
          <div className="text-xl font-bold text-purple-400 font-mono flex items-center gap-2">
            {mockArtexAnchors.length} <span className="text-xs font-normal text-slate-400">个</span>
          </div>
          <div className="text-[10px] text-purple-300 font-mono mt-1">智能体推演实时绑定</div>
        </div>
      </div>

      {/* View Switcher Bar & Filters */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-slate-900/90 p-3 rounded-2xl border border-slate-800 shadow-lg">
        {/* Tab Buttons */}
        <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('graph')}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
              activeTab === 'graph'
                ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-500/40'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Network className="w-3.5 h-3.5 text-cyan-400" />
            ARTEX 全局资产真值拓扑
          </button>
          <button
            onClick={() => setActiveTab('tree')}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
              activeTab === 'tree'
                ? 'bg-amber-500/20 text-amber-200 border border-amber-500/40'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-amber-400" />
            按任务与域名分组
          </button>
          <button
            onClick={() => setActiveTab('table')}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
              activeTab === 'table'
                ? 'bg-purple-500/20 text-purple-200 border border-purple-500/40'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Database className="w-3.5 h-3.5 text-purple-400" />
            资产真值台账清单
          </button>
        </div>

        {/* Search & Filter */}
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索 IP、域名、微服务..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
          >
            <option value="all">全量状态</option>
            <option value="has_vuln">有高危漏洞</option>
            <option value="checked">已验证正常</option>
            <option value="need_auth">需追加授权</option>
          </select>
        </div>
      </div>

      {/* TAB 1: ARTEX GLOBAL ASSET GRAPH VISUALIZER */}
      {activeTab === 'graph' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Left 8/12: Graph Visual Canvas */}
          <div className="lg:col-span-8 bg-slate-950/80 border border-slate-800 rounded-2xl p-6 relative overflow-hidden shadow-xl min-h-[500px] flex flex-col justify-between">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 z-10 relative">
              <div className="flex items-center gap-2">
                <Globe className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  全域资产关系网络 (Asset Graph: Domain ➔ Host ➔ Service ➔ Endpoint ➔ Credential)
                </h3>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                SHARED TRUTH
              </span>
            </div>

            {/* Interactive Graph Node Clusters */}
            <div className="relative z-10 py-6 space-y-6">
              {/* Layer 1: Root Domains */}
              <div className="flex items-center justify-center gap-4 flex-wrap">
                {tasks.map((t) => (
                  <div
                    key={t.id}
                    className="p-3 rounded-xl bg-slate-900 border border-cyan-500/40 shadow-md flex items-center gap-2.5 cursor-pointer hover:border-cyan-400 transition-all"
                  >
                    <Globe className="w-4 h-4 text-cyan-400" />
                    <div>
                      <div className="text-xs font-bold text-white">{t.assetTree.domain}</div>
                      <div className="text-[10px] font-mono text-cyan-300">根域名 / 入口网关</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Connecting Line */}
              <div className="flex justify-center">
                <div className="w-0.5 h-6 bg-gradient-to-b from-cyan-500/40 to-cyan-500/10" />
              </div>

              {/* Layer 2: Host Nodes */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {allHosts.slice(0, 6).map((h) => {
                  const isSelected = selectedAssetId === `host-${h.ip}`;
                  const isVuln = h.status === 'has_vuln';

                  return (
                    <div
                      key={h.ip}
                      onClick={() => setSelectedAssetId(`host-${h.ip}`)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer space-y-2 ${
                        isSelected
                          ? 'bg-slate-900 border-cyan-400 ring-2 ring-cyan-500/20 shadow-lg scale-[1.02]'
                          : isVuln
                          ? 'bg-slate-900/90 border-rose-500/40 hover:border-rose-400'
                          : 'bg-slate-900/70 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Server className={`w-3.5 h-3.5 ${isVuln ? 'text-rose-400' : 'text-slate-300'}`} />
                          <span className="font-mono text-xs font-bold text-white">{h.ip}</span>
                        </div>
                        {isVuln ? (
                          <span className="w-2 h-2 rounded-full bg-rose-400 animate-ping" />
                        ) : (
                          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                        )}
                      </div>

                      {h.hostname && (
                        <div className="text-[11px] text-slate-400 font-mono truncate">{h.hostname}</div>
                      )}

                      <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-400">
                        <span>开放端口: {h.services.map((s) => s.port).join(', ')}</span>
                        <span className="text-purple-300">已锚定</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="text-[11px] text-slate-500 text-center font-mono pt-3 border-t border-slate-800/60 z-10 relative">
              点击任意主机节点可在右侧查看其在全局资产真值库中的关联推演、开放端口与历史战果
            </div>
          </div>

          {/* Right 4/12: Asset Truth Inspector */}
          <div className="lg:col-span-4 bg-slate-900/90 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                    资产真值详情 (Truth Record)
                  </h3>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                  CONFIRMED
                </span>
              </div>

              <div className="space-y-4 pt-3 text-xs">
                <div>
                  <span className="text-slate-400 text-[11px] block mb-1">选中资产 IP / Host</span>
                  <div className="text-sm font-bold text-white font-mono">192.168.100.15</div>
                  <div className="text-xs font-mono text-cyan-300 mt-0.5">gateway-cluster-01.internal</div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                  <div className="flex justify-between">
                    <span className="text-slate-400">运行组件:</span>
                    <span className="text-white font-mono">Spring Cloud Gateway 3.1.0</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">开放服务端口:</span>
                    <span className="text-amber-300 font-mono">8080/TCP (HTTP Actuator)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">特权突破状态:</span>
                    <span className="text-rose-400 font-bold font-mono">ROOT 执行权限 (CVE-2022-22947)</span>
                  </div>
                </div>

                {/* Anchored Intent/Facts in ARTEX */}
                <div className="space-y-2">
                  <span className="text-[11px] text-slate-400 flex items-center gap-1 font-semibold">
                    <Anchor className="w-3 h-3 text-purple-400" />
                    当前锚定在该资产的 S̶h̶e̶l̶l̶ R̴e̴n 推演链
                  </span>
                  <div className="p-3 rounded-xl bg-purple-950/20 border border-purple-500/30 text-[11px] space-y-1.5">
                    <div className="text-purple-200 font-bold">• Fact: 确证 SpEL 注入代码执行</div>
                    <div className="text-purple-300/80">• Intent: 读取 /var/app/config.json 凭据</div>
                    <div className="text-[10px] font-mono text-slate-400">
                      最后同步时间: 10:05:40 · 由 Worker-01 验证确认
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-800 space-y-2">
              <button
                onClick={onOpenNewTaskModal}
                className="w-full py-2.5 px-3 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 border border-cyan-500/40 text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer shadow-md"
              >
                <Zap className="w-3.5 h-3.5" />
                针对此资产发起深度横向渗透
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: HIERARCHICAL TREE VIEW */}
      {activeTab === 'tree' && (
        <div className="space-y-4">
          {tasks.map((t) => (
            <div
              key={t.id}
              className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4 shadow-lg"
            >
              <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-slate-800">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                    <Globe className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white flex items-center gap-2">
                      <span>{t.assetTree.domain}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                        {t.code}
                      </span>
                    </div>
                    <span className="text-xs text-slate-400 font-mono">
                      关联任务: {t.name}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => onSelectTask?.(t)}
                    className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-semibold border border-slate-700 transition-colors cursor-pointer"
                  >
                    在作战室查看完整拓扑
                  </button>
                </div>
              </div>

              {/* Host Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {(t.assetTree.hosts || []).map((h) => (
                  <div
                    key={h.ip}
                    className={`p-3.5 rounded-xl border text-xs space-y-2 ${
                      h.status === 'has_vuln'
                        ? 'bg-slate-950/80 border-rose-500/40 shadow-sm shadow-rose-950/20'
                        : h.status === 'need_auth'
                        ? 'bg-slate-950/80 border-amber-500/40'
                        : 'bg-slate-950/60 border-slate-800'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-slate-200">
                        {h.ip}
                      </span>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                          h.status === 'has_vuln'
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                            : h.status === 'need_auth'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        }`}
                      >
                        {h.status === 'has_vuln'
                          ? '有高危发现'
                          : h.status === 'need_auth'
                          ? '需追加授权'
                          : '已安全探测'}
                      </span>
                    </div>

                    {h.hostname && (
                      <div className="text-[11px] text-slate-400 truncate">
                        {h.hostname}
                      </div>
                    )}

                    <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                      <span>开放端口: {h.services?.length || 0} 个</span>
                      <span className="text-cyan-300">
                        {h.services?.map((s) => s.port).join(', ') || 'N/A'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 3: ASSET TRUTH INVENTORY TABLE */}
      {activeTab === 'table' && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-mono">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">主机 IP / 主机名</th>
                  <th className="py-3.5 px-4 font-semibold">真值状态</th>
                  <th className="py-3.5 px-4 font-semibold">开放服务与端口</th>
                  <th className="py-3.5 px-4 font-semibold">ARTEX 锚定意图</th>
                  <th className="py-3.5 px-4 font-semibold text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {filteredHosts.map((h) => (
                  <tr key={h.ip} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-mono font-bold text-white">{h.ip}</div>
                      <div className="text-[11px] text-slate-400">{h.hostname || '未解析 PTR'}</div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-full inline-block ${
                          h.status === 'has_vuln'
                            ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                            : h.status === 'need_auth'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        }`}
                      >
                        {h.status === 'has_vuln'
                          ? '有高危漏洞'
                          : h.status === 'need_auth'
                          ? '需追加授权'
                          : '已确证正常'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-300">
                      {h.services?.map((s) => `${s.port}/${s.protocol} (${s.service})`).join(', ') || '暂无开放端口'}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="text-[11px] text-purple-300 font-mono flex items-center gap-1">
                        <Anchor className="w-3 h-3 text-purple-400" />
                        已同步到全局真值库
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={onOpenNewTaskModal}
                        className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 font-semibold text-xs border border-slate-700 transition-colors cursor-pointer"
                      >
                        发起扫描
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
