import React, { useState } from 'react';
import {
  Cpu,
  Sparkles,
  ShieldCheck,
  Zap,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  GitBranch,
  Terminal,
  Save,
  Compass,
  Layers,
  GitCommit,
  ExternalLink,
  Bot,
  Flame,
  Check,
  Anchor,
  ListOrdered,
  RefreshCw,
} from 'lucide-react';
import { AIModelConfig, ArtexConfig } from '../types';

interface AICenterViewProps {
  config: AIModelConfig;
  onUpdateConfig: (newConfig: AIModelConfig) => void;
}

export const AICenterView: React.FC<AICenterViewProps> = ({
  config,
  onUpdateConfig,
}) => {
  const [localConfig, setLocalConfig] = useState<AIModelConfig>(config);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    onUpdateConfig(localConfig);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const cairn = localConfig.cairnSearchConfig || {
    searchStrategy: 'heuristic_astar',
    workerBackend: 'claude_code',
    originTarget: '10.240.0.1 (DMZ Entrypoint)',
    goalState: 'Active Directory Domain Controller (Domain Admin Privileges)',
    factCount: 18,
    intentCount: 6,
    hintCount: 4,
    pruningThreshold: 0.85,
    maxSearchDepth: 10,
    backtrackingEnabled: true,
  };

  const artex = localConfig.artexConfig || {
    plannerModel: 'ARTEX-MultiAgent-Planner-v3.2',
    maxSubTasks: 12,
    autoAnchoring: true,
    dualGraphSync: true,
    crossTaskAssetInheritance: true,
    replanOnFailure: true,
  };

  const updateCairn = (field: string, value: any) => {
    setLocalConfig({
      ...localConfig,
      cairnSearchConfig: {
        ...cairn,
        [field]: value,
      },
    });
  };

  const updateArtex = (field: string, value: any) => {
    setLocalConfig({
      ...localConfig,
      artexConfig: {
        ...artex,
        [field]: value,
      },
    });
  };

  return (
    <div className="flex-1 p-5 md:p-8 overflow-y-auto text-slate-100 space-y-6 max-w-5xl mx-auto z-10 relative pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 font-bold">
              ARTEX × CAIRN × 雲頂天宮
            </span>
            <span className="text-xs text-slate-400 font-mono">
              S̶h̶e̶l̶l̶ R̴e̴n 智能体协同与规划控制中心
            </span>
          </div>
          <h1 className="text-xl font-bold text-white tracking-wide flex items-center gap-2">
            S̶h̶e̶l̶l̶ R̴e̴n 智能体架构与双图规划引擎
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            整合 ARTEX 双图架构与共享任务清单 + Cairn 状态空间启发式搜索与确定性事实推演
          </p>
        </div>

        <button
          onClick={handleSave}
          className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black transition-all shadow-md flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          <Save className="w-4 h-4" />
          {saved ? '配置已保存生效' : '保存智能体配置'}
        </button>
      </div>

      {/* 1. ARTEX Dual-Graph & Multi-Agent Planner Integration */}
      <div className="p-6 rounded-2xl bg-slate-900/85 backdrop-blur-sm border border-cyan-500/30 space-y-5 shadow-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Anchor className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold text-white">
              ARTEX 双图联动与 Planner 规划器配置
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="https://artex-demo.vercel.app/"
              target="_blank"
              rel="noreferrer"
              className="text-[11px] font-mono text-cyan-300 hover:text-cyan-200 flex items-center gap-1 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20"
            >
              ARTEX 演示 <ExternalLink className="w-3 h-3" />
            </a>
            <a
              href="https://github.com/Autumn-27/ARTEX"
              target="_blank"
              rel="noreferrer"
              className="text-[11px] font-mono text-cyan-300 hover:text-cyan-200 flex items-center gap-1 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20"
            >
              Autumn-27/ARTEX 源码 <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">
              Planner 规划模型 (Shared To-Do List Planner):
            </label>
            <select
              value={artex.plannerModel}
              onChange={(e) => updateArtex('plannerModel', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-cyan-500/50"
            >
              <option value="ARTEX-MultiAgent-Planner-v3.2">ARTEX-MultiAgent-Planner-v3.2 (推荐)</option>
              <option value="ARTEX-Stealth-RedTeam-v1">ARTEX-Stealth-RedTeam-v1 (低流量避障模式)</option>
              <option value="ARTEX-Aggressive-Poc-v2">ARTEX-Aggressive-Poc-v2 (靶场快速突破)</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">
              单次规划最大子任务步长 (Max Sub-Tasks per Plan):
            </label>
            <input
              type="number"
              min="4"
              max="30"
              value={artex.maxSubTasks}
              onChange={(e) => updateArtex('maxSubTasks', parseInt(e.target.value) || 12)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-cyan-500/50"
            />
          </div>
        </div>

        {/* Toggles */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
          <label className="flex items-center justify-between p-3 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer">
            <div>
              <div className="text-xs font-bold text-slate-200">
                启用双图自动锚定 (Auto-Anchoring)
              </div>
              <div className="text-[10px] text-slate-400">
                将探索图中的 Intent/Fact 自动映射至 Asset Graph 端口端点
              </div>
            </div>
            <input
              type="checkbox"
              checked={artex.autoAnchoring}
              onChange={(e) => updateArtex('autoAnchoring', e.target.checked)}
              className="w-4 h-4 accent-cyan-500"
            />
          </label>

          <label className="flex items-center justify-between p-3 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer">
            <div>
              <div className="text-xs font-bold text-slate-200">
                跨任务资产真值库继承 (Cross-Task Shared Truth)
              </div>
              <div className="text-[10px] text-slate-400">
                不同渗透任务之间共享已确认的全局资产树与存活拓扑
              </div>
            </div>
            <input
              type="checkbox"
              checked={artex.crossTaskAssetInheritance}
              onChange={(e) => updateArtex('crossTaskAssetInheritance', e.target.checked)}
              className="w-4 h-4 accent-cyan-500"
            />
          </label>
        </div>
      </div>

      {/* 2. Cairn State Space Search Engine Integration */}
      <div className="p-6 rounded-2xl bg-slate-900/85 backdrop-blur-sm border border-purple-500/30 space-y-5 shadow-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Compass className="w-4 h-4 text-purple-400" />
            <h2 className="text-sm font-bold text-white">
              Cairn 状态空间搜索配置 (State-Space Search Engine)
            </h2>
          </div>
          <a
            href="https://github.com/oritera/Cairn"
            target="_blank"
            rel="noreferrer"
            className="text-[11px] font-mono text-purple-300 hover:text-purple-200 flex items-center gap-1 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20"
          >
            oritera/Cairn 源码 <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        {/* Origin & Goal Definition */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
              <span>起点状态 (Origin State):</span>
              <span className="text-[10px] text-cyan-400 font-mono">入口/DMZ</span>
            </label>
            <input
              type="text"
              value={cairn.originTarget}
              onChange={(e) => updateCairn('originTarget', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-purple-500/50"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
              <span>目标状态 (Goal State):</span>
              <span className="text-[10px] text-amber-400 font-mono">靶心目标</span>
            </label>
            <input
              type="text"
              value={cairn.goalState}
              onChange={(e) => updateCairn('goalState', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-purple-500/50"
            />
          </div>
        </div>

        {/* Search Strategy & Worker Backend */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">
              启发式路径搜索策略：
            </label>
            <select
              value={cairn.searchStrategy}
              onChange={(e) => updateCairn('searchStrategy', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-purple-500/50"
            >
              <option value="heuristic_astar">A* 启发式剪枝搜索 (推荐 - 速度与完备性最优)</option>
              <option value="mcts_goal_oriented">MCTS 蒙特卡洛目标导向树搜索 (对抗环境防 WAF)</option>
              <option value="depth_first_path">目标优先深度优先遍历 (针对单点高危突破)</option>
              <option value="breadth_first_recon">广度优先全量资产扫描 (信息搜集阶段)</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">
              执行 Worker 后端：
            </label>
            <select
              value={cairn.workerBackend}
              onChange={(e) => updateCairn('workerBackend', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-100 font-mono focus:border-purple-500/50"
            >
              <option value="claude_code">Claude Code Worker (Cairn 原生集成终端智能体)</option>
              <option value="codex_reasoner">OpenAI Codex / Reasoner (高阶漏洞利用链生成)</option>
              <option value="pi_agent">Pi Agent (轻量级探测与快速事实搜集)</option>
              <option value="sandbox_container">安全沙箱 PoC 执行环境 (本地沙箱容器)</option>
            </select>
          </div>
        </div>

        {/* Backtracking & Pruning */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
          <label className="flex items-center justify-between p-3 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer">
            <div>
              <div className="text-xs font-bold text-slate-200">
                支持状态空间自动回溯 (Backtracking)
              </div>
              <div className="text-[10px] text-slate-400">
                遇到 WAF 拦截或死胡同时自动回退至上一有效分支
              </div>
            </div>
            <input
              type="checkbox"
              checked={cairn.backtrackingEnabled}
              onChange={(e) => updateCairn('backtrackingEnabled', e.target.checked)}
              className="w-4 h-4 accent-purple-500"
            />
          </label>

          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <div className="flex justify-between text-xs font-bold text-slate-200">
              <span>剪枝置信度阈值 (Pruning)</span>
              <span className="font-mono text-purple-300">{cairn.pruningThreshold}</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="0.99"
              step="0.05"
              value={cairn.pruningThreshold}
              onChange={(e) => updateCairn('pruningThreshold', parseFloat(e.target.value))}
              className="w-full accent-purple-500 cursor-pointer"
            />
          </div>
        </div>
      </div>

      {/* 3. S̶h̶e̶l̶l̶ R̴e̴n 大模型底座 */}
      <div className="p-6 rounded-2xl bg-slate-900/85 backdrop-blur-sm border border-slate-800 space-y-5 shadow-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <h2 className="text-sm font-bold text-white">S̶h̶e̶l̶l̶ R̴e̴n 底座模型与攻防思维链</h2>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            S̶h̶e̶l̶l̶ R̴e̴n READY
          </span>
        </div>

        <div className="space-y-3">
          <label className="text-xs font-semibold text-slate-300 block">
            当前激活的 S̶h̶e̶l̶l̶ R̴e̴n 模型：
          </label>
          <select
            value={localConfig.activeModel}
            onChange={(e) =>
              setLocalConfig({ ...localConfig, activeModel: e.target.value })
            }
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-amber-500/50"
          >
            {localConfig.availableModels.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 4. Autonomy Level */}
      <div className="p-6 rounded-2xl bg-slate-900/85 backdrop-blur-sm border border-slate-800 space-y-5 shadow-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold text-white">自主攻击与越界审批策略</h2>
          </div>
          <span className="text-xs font-mono text-amber-300">
            {localConfig.autonomyLevel === 'semi_auto'
              ? '半自动模式 (高危需指挥官授权)'
              : localConfig.autonomyLevel === 'full_auto'
              ? '全自主攻防 (完全放行)'
              : '专家向导模式'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            {
              id: 'semi_auto',
              title: '半自动 (Semi-Auto)',
              desc: '常规探测自主推进，涉及越界扩展与破坏性提权必须通过人工确认放行。',
            },
            {
              id: 'full_auto',
              title: '全自动 (Full-Autonomous)',
              desc: 'S̶h̶e̶l̶l̶ R̴e̴n 自主制定攻击链并直接执行 PoC，适用于授权闭环靶场环境。',
            },
            {
              id: 'guided',
              title: '专家向导 (Guided)',
              desc: 'S̶h̶e̶l̶l̶ R̴e̴n 仅提供推理建议与 Payload 推荐，每一步工具执行需人工手动触发。',
            },
          ].map((lvl) => (
            <div
              key={lvl.id}
              onClick={() =>
                setLocalConfig({
                  ...localConfig,
                  autonomyLevel: lvl.id as any,
                })
              }
              className={`p-4 rounded-xl border transition-all cursor-pointer select-none space-y-2 ${
                localConfig.autonomyLevel === lvl.id
                  ? 'bg-amber-500/10 border-amber-400 shadow-md ring-1 ring-amber-500/30'
                  : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="text-xs font-bold text-white">{lvl.title}</div>
              <p className="text-[11px] text-slate-400 leading-relaxed">{lvl.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 5. Safety Guardrails & Anti-Hallucination */}
      <div className="p-6 rounded-2xl bg-slate-900/85 backdrop-blur-sm border border-slate-800 space-y-4 shadow-xl">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-bold text-white">安全红线与抗幻觉双重校验</h2>
        </div>

        <div className="space-y-3">
          <label className="flex items-center justify-between p-3.5 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer">
            <div>
              <div className="text-xs font-bold text-slate-200">
                强制事实验证 (Anti-Hallucination Double Check)
              </div>
              <div className="text-[11px] text-slate-400">
                漏洞必须通过确定性回显二次测试，杜绝 S̶h̶e̶l̶l̶ R̴e̴n 虚报自嗨
              </div>
            </div>
            <input
              type="checkbox"
              checked={localConfig.antiHallucinationDoubleCheck}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  antiHallucinationDoubleCheck: e.target.checked,
                })
              }
              className="w-4 h-4 accent-amber-500"
            />
          </label>

          <label className="flex items-center justify-between p-3.5 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer">
            <div>
              <div className="text-xs font-bold text-slate-200">
                严格遵循授权边界 (Scope Guard)
              </div>
              <div className="text-[11px] text-slate-400">
                探测超出初始目标网段时自动触发 Mission Grant 阻断审批
              </div>
            </div>
            <input
              type="checkbox"
              checked={localConfig.safetyGuardrails}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  safetyGuardrails: e.target.checked,
                })
              }
              className="w-4 h-4 accent-amber-500"
            />
          </label>
        </div>
      </div>
    </div>
  );
};
