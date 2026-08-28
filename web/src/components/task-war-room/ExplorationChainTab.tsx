import React, { useState } from 'react';
import {
  GitCommit,
  ArrowDown,
  ArrowRight,
  ShieldAlert,
  Server,
  Key,
  Database,
  Cpu,
  ChevronRight,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Compass,
  Layers,
  HelpCircle,
  Lightbulb,
  ListOrdered,
  Anchor,
  Send,
  RefreshCw,
  Clock,
  Play,
  RotateCcw,
  Zap,
  Target,
  FileCode,
  Globe,
  ExternalLink,
} from 'lucide-react';
import {
  ChainNode,
  ChainEdge,
  SeverityLevel,
  ArtexPlannerItem,
  ArtexDualGraphNode,
  ArtexDualGraphEdge,
  ArtexAnchor,
} from '../../types';
import {
  mockFactGraphItems,
  mockArtexPlannerItems,
  mockArtexDualGraphNodes,
  mockArtexDualGraphEdges,
  mockArtexAnchors,
} from '../../data/mockData';

interface ExplorationChainTabProps {
  nodes: ChainNode[];
  edges: ChainEdge[];
  onViewEvidence?: (evidenceId: string) => void;
}

export const ExplorationChainTab: React.FC<ExplorationChainTabProps> = ({
  nodes,
  edges,
  onViewEvidence,
}) => {
  const [viewMode, setViewMode] = useState<'artex_dual_graph' | 'artex_planner' | 'cairn_topology'>('artex_dual_graph');
  
  // Dual-graph selection state
  const [selectedDualNodeId, setSelectedDualNodeId] = useState<string>('node-fact-1');
  const [selectedAnchorId, setSelectedAnchorId] = useState<string | null>(null);

  // Planner state
  const [plannerItems, setPlannerItems] = useState<ArtexPlannerItem[]>(mockArtexPlannerItems);
  const [selectedPlanItem, setSelectedPlanItem] = useState<ArtexPlannerItem | null>(mockArtexPlannerItems[1]);
  const [newHintInput, setNewHintInput] = useState('');
  const [hintSentSuccess, setHintSentSuccess] = useState(false);

  // Topology node selection
  const [selectedTopologyNodeId, setSelectedTopologyNodeId] = useState<string>(
    nodes[nodes.length - 1]?.id || nodes[0]?.id || ''
  );

  const selectedTopologyNode = nodes.find((n) => n.id === selectedTopologyNodeId);
  const selectedDualNode = mockArtexDualGraphNodes.find((n) => n.id === selectedDualNodeId);
  const matchingAnchor = mockArtexAnchors.find((a) => a.explorationNodeId === selectedDualNodeId);

  const handleAddHint = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newHintInput.trim()) return;

    const newPlanner: ArtexPlannerItem = {
      id: `plan-hint-${Date.now()}`,
      order: plannerItems.length + 1,
      title: `[指挥官战术指令] ${newHintInput}`,
      phase: 'privilege_escalation',
      status: 'pending',
      targetAnchor: '指挥官实时指定的关键资产',
      confidence: 1.0,
      assignedWorker: 'Worker-01 (Primary Pivot)',
      rationale: '人工实时介入注入的高优先级线索，S̶h̶e̶l̶l̶ R̴e̴n 将在下一轮规划中优先解析执行。',
      duration: '刚插入',
      outputPreview: '等待 Worker 排程执行',
    };

    setPlannerItems([newPlanner, ...plannerItems]);
    setNewHintInput('');
    setHintSentSuccess(true);
    setTimeout(() => setHintSentSuccess(false), 2500);
  };

  const getPhaseBadge = (phase: ArtexPlannerItem['phase']) => {
    switch (phase) {
      case 'recon':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">资产侦察</span>;
      case 'fingerprint':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">指纹识别</span>;
      case 'poc_verify':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">PoC事实验证</span>;
      case 'privilege_escalation':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">提权突破</span>;
      case 'lateral_movement':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">横向移动</span>;
      case 'exfiltration':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">靶心战果</span>;
      default:
        return null;
    }
  };

  const getPlannerStatusIcon = (status: ArtexPlannerItem['status']) => {
    switch (status) {
      case 'succeeded':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'in_progress':
        return <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping" />;
      case 'blocked':
        return <AlertTriangle className="w-4 h-4 text-amber-400" />;
      case 'backtracked':
        return <RotateCcw className="w-4 h-4 text-slate-500" />;
      case 'pending':
      default:
        return <Clock className="w-4 h-4 text-slate-600" />;
    }
  };

  const getDualNodeBadge = (type: ArtexDualGraphNode['type']) => {
    switch (type) {
      case 'goal':
        return <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">GOAL 目标</span>;
      case 'intent':
        return <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">INTENT 意图假设</span>;
      case 'fact':
        return <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">FACT 确证事实</span>;
      case 'finding':
        return <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">FINDING 漏洞战果</span>;
      case 'hint':
        return <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">HINT 指挥官线索</span>;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-5 max-w-6xl mx-auto pb-10">
      {/* Top Banner with 3 Exploration Modes */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <Compass className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white tracking-wide">
                ARTEX 双图联动 & 规划器推演控制台
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                ARTEX × CAIRN
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              融合「全局资产真值库 (Asset Graph) ↔ 任务独立探索图 (Exploration Graph) ↔ 共享任务清单 (Planner)」
            </p>
          </div>
        </div>

        {/* 3 Mode Selector Pills */}
        <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 self-stretch sm:self-auto overflow-x-auto">
          <button
            onClick={() => setViewMode('artex_dual_graph')}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
              viewMode === 'artex_dual_graph'
                ? 'bg-purple-500/20 text-purple-200 border border-purple-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Anchor className="w-3.5 h-3.5 text-purple-400" />
            ARTEX 双图锚点联动
          </button>
          
          <button
            onClick={() => setViewMode('artex_planner')}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
              viewMode === 'artex_planner'
                ? 'bg-amber-500/20 text-amber-200 border border-amber-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <ListOrdered className="w-3.5 h-3.5 text-amber-400" />
            Planner 共享任务清单
          </button>

          <button
            onClick={() => setViewMode('cairn_topology')}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
              viewMode === 'cairn_topology'
                ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <GitCommit className="w-3.5 h-3.5 text-cyan-400" />
            Cairn 状态空间拓扑
          </button>
        </div>
      </div>

      {/* MODE 1: ARTEX DUAL GRAPH & ANCHOR EXPLORER */}
      {viewMode === 'artex_dual_graph' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Left Col (7/12): Exploration Graph (Goals -> Intents -> Facts -> Findings) */}
            <div className="lg:col-span-7 bg-slate-950/80 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-xl flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                      1. 任务独立推演图 (Exploration Graph)
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono text-slate-400">
                    {mockArtexDualGraphNodes.length} 核心推演节点 · {mockArtexDualGraphEdges.length} 逻辑因果边
                  </span>
                </div>

                {/* Nodes List */}
                <div className="space-y-3 pt-3">
                  {mockArtexDualGraphNodes.map((node) => {
                    const isSelected = selectedDualNodeId === node.id;
                    const hasAnchor = mockArtexAnchors.some((a) => a.explorationNodeId === node.id);

                    return (
                      <div
                        key={node.id}
                        onClick={() => setSelectedDualNodeId(node.id)}
                        className={`p-3.5 rounded-xl border transition-all cursor-pointer space-y-2 ${
                          isSelected
                            ? 'bg-purple-950/30 border-purple-500 ring-2 ring-purple-500/30 shadow-lg'
                            : 'bg-slate-900/80 border-slate-800 hover:border-slate-700 hover:bg-slate-900'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            {getDualNodeBadge(node.type)}
                            <span className="text-xs font-bold text-slate-100">{node.title}</span>
                          </div>
                          {hasAnchor && (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 flex items-center gap-1 shrink-0">
                              <Anchor className="w-2.5 h-2.5" />
                              已锚定资产
                            </span>
                          )}
                        </div>

                        <p className="text-[11px] text-slate-400 leading-relaxed pl-1">
                          {node.description}
                        </p>

                        {node.anchoredAssetLabel && (
                          <div className="flex items-center gap-2 text-[10px] font-mono text-purple-300 bg-purple-500/10 px-2.5 py-1 rounded-lg border border-purple-500/20">
                            <span className="text-slate-400">双图锚点目标:</span>
                            <span className="font-bold">{node.anchoredAssetLabel}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="text-[11px] text-slate-500 text-center font-mono pt-3 border-t border-slate-800">
                ARTEX 架构规范：Exploration Graph 记录单任务推演，通过 Anchors 与全局 Asset Graph 保持双向解耦与联动
              </div>
            </div>

            {/* Right Col (5/12): Asset Graph Anchor Inspector & Verified Proof */}
            <div className="lg:col-span-5 bg-slate-900/90 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-xl flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Anchor className="w-4 h-4 text-cyan-400" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                      2. 全局资产真值库锚点 (Asset Graph Anchor)
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                    REAL-TIME SYNC
                  </span>
                </div>

                {selectedDualNode ? (
                  <div className="space-y-4 pt-3 text-xs">
                    <div>
                      <span className="text-slate-400 text-[11px] block mb-1">当前选中的推演节点</span>
                      <div className="text-sm font-bold text-white">{selectedDualNode.title}</div>
                      <div className="text-slate-300 mt-1 leading-relaxed">{selectedDualNode.description}</div>
                    </div>

                    {matchingAnchor ? (
                      <div className="p-4 rounded-xl bg-slate-950 border border-cyan-500/30 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-cyan-300 flex items-center gap-1.5">
                            <Anchor className="w-3.5 h-3.5" /> 资产真值锚定状态 (Anchor Verified)
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 uppercase">
                            {matchingAnchor.assetType}
                          </span>
                        </div>

                        <div className="space-y-1.5 text-[11px]">
                          <div className="flex justify-between">
                            <span className="text-slate-400">宿主资产:</span>
                            <span className="text-slate-200 font-mono font-bold">{matchingAnchor.assetTarget}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">锚定原由:</span>
                            <span className="text-slate-300">{matchingAnchor.anchorReason}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">真值沉淀:</span>
                            <span className="text-emerald-400 font-mono font-semibold">已写入全局共享资产库</span>
                          </div>
                        </div>

                        <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-slate-400">
                          💡 该资产上的推演事实（CVE-2022-22947 / 内存密钥）已自动同步至全域资产库，其他任务再次探测该网段时无需重复扫描。
                        </div>
                      </div>
                    ) : (
                      <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center text-slate-500">
                        当前推演节点暂未绑定具体单点资产（属于高阶顶层规划或战术原则）
                      </div>
                    )}

                    {/* Quick Action */}
                    <div className="space-y-2 pt-2">
                      <div className="text-[11px] text-slate-400">S̶h̶e̶l̶l̶ R̴e̴n 自动化行动判定</div>
                      <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 font-mono text-[11px] text-emerald-300 space-y-1">
                        <div>&gt; target_host: 192.168.100.15</div>
                        <div>&gt; exploit_state: REPRODUCIBLE_CONFIRMED</div>
                        <div>&gt; pivot_status: ESTABLISHED (SOCKS5 10808)</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 text-xs">
                    请在左侧选择推演节点查看双图锚点详情
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-slate-800">
                <button
                  onClick={() => onViewEvidence?.('ev-01')}
                  className="w-full py-2.5 px-4 rounded-xl bg-purple-500/20 hover:bg-purple-500/30 text-purple-200 border border-purple-500/40 text-xs font-bold transition-all flex items-center justify-center gap-2 cursor-pointer shadow-md"
                >
                  <Key className="w-4 h-4 text-purple-400" />
                  查看关联确证证据 (ID: ev-01)
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODE 2: ARTEX PLANNER SHARED TO-DO LIST */}
      {viewMode === 'artex_planner' && (
        <div className="space-y-5">
          {/* Commander Hint Injection Box */}
          <form
            onSubmit={handleAddHint}
            className="p-4 rounded-2xl bg-slate-900/90 border border-amber-500/30 shadow-lg space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-amber-400" />
                <h3 className="text-xs font-bold text-white">
                  指挥官实时战术线索注入 (Planner In-the-Loop Directive)
                </h3>
              </div>
              <span className="text-[10px] font-mono text-amber-300 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
                HIGH-PRIORITY INJECT
              </span>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                value={newHintInput}
                onChange={(e) => setNewHintInput(e.target.value)}
                placeholder="例如：优先尝试 10.244.10.0/24 核心财务段，规避 192.168.100.88 历史蜜罐..."
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/50"
              />
              <button
                type="submit"
                className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs transition-all flex items-center gap-1.5 cursor-pointer shadow-md shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
                注入到 Planner 清单
              </button>
            </div>

            {hintSentSuccess && (
              <div className="text-xs text-emerald-400 flex items-center gap-1.5 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                战术线索已成功注入，S̶h̶e̶l̶l̶ R̴e̴n Planner 已将其提升为最高优先级执行项！
              </div>
            )}
          </form>

          {/* Planner Table / Card Flow */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Left 7/12: To-Do Items List */}
            <div className="lg:col-span-7 bg-slate-950/80 border border-slate-800 rounded-2xl p-5 space-y-3 shadow-xl">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <ListOrdered className="w-4 h-4 text-amber-400" />
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                    ARTEX 攻击链规划清单 (Shared To-Do List)
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-slate-400">
                  {plannerItems.filter((i) => i.status === 'succeeded').length}/{plannerItems.length} 已完成
                </span>
              </div>

              <div className="space-y-2.5">
                {plannerItems.map((item, idx) => {
                  const isSelected = selectedPlanItem?.id === item.id;

                  return (
                    <div
                      key={item.id}
                      onClick={() => setSelectedPlanItem(item)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                        isSelected
                          ? 'bg-slate-900 border-amber-400 ring-2 ring-amber-500/20 shadow-md'
                          : item.status === 'backtracked'
                          ? 'bg-slate-950/60 border-slate-800/80 opacity-60'
                          : 'bg-slate-900/70 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-6 h-6 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                          {getPlannerStatusIcon(item.status)}
                        </div>

                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-bold text-white truncate">
                              #{item.order} {item.title}
                            </span>
                            {getPhaseBadge(item.phase)}
                          </div>
                          <div className="text-[11px] text-slate-400 font-mono truncate mt-0.5">
                            目标锚点: {item.targetAnchor} · 执行节点: {item.assignedWorker}
                          </div>
                        </div>
                      </div>

                      <div className="text-right shrink-0">
                        <span className="text-[10px] font-mono text-slate-400 block">{item.duration}</span>
                        <ChevronRight className="w-4 h-4 text-slate-500 inline-block mt-0.5" />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right 5/12: Plan Item Inspector */}
            <div className="lg:col-span-5 bg-slate-900/90 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-xl flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Target className="w-4 h-4 text-amber-400" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                      规划子任务详情
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                    STEP #{selectedPlanItem?.order}
                  </span>
                </div>

                {selectedPlanItem ? (
                  <div className="space-y-4 pt-3 text-xs">
                    <div>
                      <div className="text-sm font-bold text-white">{selectedPlanItem.title}</div>
                      <div className="flex items-center gap-2 mt-1.5">
                        {getPhaseBadge(selectedPlanItem.phase)}
                        <span className="text-[11px] font-mono text-amber-300">
                          置信度: {(selectedPlanItem.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                      <div className="flex justify-between">
                        <span className="text-slate-400">分配 Worker:</span>
                        <span className="text-slate-200 font-mono font-semibold">{selectedPlanItem.assignedWorker}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">目标资产锚点:</span>
                        <span className="text-cyan-300 font-mono truncate max-w-[200px]">{selectedPlanItem.targetAnchor}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">执行状态:</span>
                        <span className="font-bold text-white capitalize">{selectedPlanItem.status}</span>
                      </div>
                    </div>

                    <div>
                      <span className="text-slate-400 text-[11px] block mb-1">AI 规划推理依据 (Rationale)</span>
                      <p className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 leading-relaxed text-[11px]">
                        {selectedPlanItem.rationale}
                      </p>
                    </div>

                    {selectedPlanItem.outputPreview && (
                      <div>
                        <span className="text-slate-400 text-[11px] block mb-1">执行回显摘要 / 战果确证</span>
                        <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono text-[11px] text-emerald-300 leading-relaxed">
                          {selectedPlanItem.outputPreview}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-500 text-xs">
                    请在左侧选择子任务查看详细规划与回显
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-slate-800 text-[11px] text-slate-500 font-mono text-center">
                ARTEX Planner 机制：单项失败自动触发 Backtracking 状态回溯与动态重新规划 (Re-plan)
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODE 3: CAIRN TOPOLOGY & STATE SPACE TREE */}
      {viewMode === 'cairn_topology' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Left 2 Cols: Visual Tree Topology Map */}
          <div className="lg:col-span-2 bg-slate-950/80 border border-slate-800 rounded-2xl p-6 relative overflow-hidden shadow-xl min-h-[520px] flex flex-col justify-between">
            {/* Graph Nodes Visual Tree Flow */}
            <div className="relative z-10 flex flex-col items-center space-y-3 py-2">
              {nodes.map((node, index) => {
                const isSelected = selectedTopologyNodeId === node.id;
                const isLast = index === nodes.length - 1;
                const hasCritical = node.severity === 'CRITICAL';

                return (
                  <React.Fragment key={node.id}>
                    {/* The Node Box */}
                    <div
                      onClick={() => setSelectedTopologyNodeId(node.id)}
                      className={`group cursor-pointer w-full max-w-md p-3.5 rounded-xl border transition-all duration-200 flex items-center justify-between ${
                        isSelected
                          ? 'bg-slate-900 border-cyan-400 ring-2 ring-cyan-500/20 shadow-lg shadow-cyan-950/40 scale-[1.02]'
                          : hasCritical
                          ? 'bg-slate-900/90 border-rose-500/50 hover:border-rose-400 shadow-sm shadow-rose-950/20'
                          : 'bg-slate-900/70 border-slate-800 hover:border-slate-700 hover:bg-slate-900'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={`w-8 h-8 rounded-lg flex items-center justify-center border shrink-0 ${
                            isSelected
                              ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300'
                              : 'bg-slate-800/80 border-slate-700 text-slate-300'
                          }`}
                        >
                          <GitCommit className="w-4 h-4" />
                        </div>

                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-xs font-bold truncate ${
                                isSelected ? 'text-cyan-300' : 'text-slate-100'
                              }`}
                            >
                              {node.label}
                            </span>
                            {node.severity && (
                              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                                {node.severity}
                              </span>
                            )}
                          </div>
                          {node.subLabel && (
                            <span className="text-[11px] text-slate-400 font-mono block truncate">
                              {node.subLabel}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {node.status === 'confirmed' ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        ) : node.status === 'active' ? (
                          <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
                        ) : (
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                        )}
                        <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-slate-300 transition-colors" />
                      </div>
                    </div>

                    {/* Vertical Connector Arrow */}
                    {!isLast && (
                      <div className="flex flex-col items-center justify-center my-0.5">
                        <div className="w-0.5 h-4 bg-gradient-to-b from-cyan-500/60 to-cyan-500/20" />
                        <ArrowDown className="w-3.5 h-3.5 text-cyan-500/60 -mt-1" />
                      </div>
                    )}
                  </React.Fragment>
                );
              })}
            </div>

            <div className="text-[11px] text-slate-500 text-center font-mono mt-4 pt-2 border-t border-slate-800/60">
              Cairn 状态空间模型：Origin Target ➔ Heuristic A* Pruning ➔ Goal State
            </div>
          </div>

          {/* Right 1 Col: Node Inspector */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-sm font-bold text-white">推演节点详情</h3>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  {selectedTopologyNode?.type?.toUpperCase()}
                </span>
              </div>

              {selectedTopologyNode ? (
                <div className="space-y-4 text-xs">
                  <div>
                    <span className="text-slate-400 text-[11px] block mb-1">节点名称</span>
                    <div className="text-sm font-bold text-white">{selectedTopologyNode.label}</div>
                    <div className="text-xs font-mono text-cyan-300 mt-0.5">
                      {selectedTopologyNode.subLabel}
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-slate-400">状态</span>
                      <span className="text-emerald-400 font-semibold flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> 已完成事实验证
                      </span>
                    </div>
                    {selectedTopologyNode.severity && (
                      <div className="flex justify-between">
                        <span className="text-slate-400">风险等级</span>
                        <span className="text-rose-400 font-bold font-mono">
                          {selectedTopologyNode.severity}
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-slate-400">推理置信度</span>
                      <span className="text-cyan-300 font-mono font-bold">100% (确定性验证)</span>
                    </div>
                  </div>

                  <div>
                    <span className="text-slate-400 text-[11px] block mb-1">S̶h̶e̶l̶l̶ R̴e̴n 判定逻辑</span>
                    <p className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 leading-relaxed">
                      S̶h̶e̶l̶l̶ R̴e̴n 自动化完成指纹比对并注入 PoC，直接拿到高权限回显，确认该攻击路径可稳定复现，已记录至 雲頂天宮 全局资产与推演图谱。
                    </p>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-slate-500">
                  请在左侧选择一个节点以查看详细推演
                </div>
              )}
            </div>

            {selectedTopologyNode?.evidenceId && (
              <div className="pt-4 border-t border-slate-800 mt-4">
                <button
                  onClick={() => onViewEvidence?.(selectedTopologyNode.evidenceId!)}
                  className="w-full py-2 px-3 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30 text-xs font-bold transition-colors flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Key className="w-3.5 h-3.5 text-cyan-400" />
                  查看关联硬核证据 (ID: {selectedTopologyNode.evidenceId})
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
