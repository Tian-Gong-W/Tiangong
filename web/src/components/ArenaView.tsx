import React, { useState, useEffect } from 'react';
import {
  Swords,
  Trophy,
  Shield,
  Zap,
  Activity,
  Flame,
  Crown,
  Sparkles,
  Skull,
  Clock,
  Cpu,
  Layers,
  RefreshCw,
  Crosshair,
  Database,
  Globe,
  Key,
  Play,
  Pause,
} from 'lucide-react';
import {
  getArenaStatus,
  simulateArenaRound,
  executeTacticalCombat,
  toggleAutoSimulate,
  subscribeArenaStream,
} from '../api';

interface Strategist {
  id: string;
  name: string;
  model: string;
  avatarIcon: string;
  avatarColor: string;
  isLeader: boolean;
  score: number;
  accuracy: number; // 理论准确度
  successRate: number; // 执行成功率
  riskReward: number; // 风险收益比
  wins: number;
  totalRounds: number;
  tacticalMode: string;
  equippedSkills: string[];
  recentDecision: string;
}

interface SubagentLoot {
  id: string;
  code: string;
  name: string;
  assignedTo: string;
  ttlRemaining: number;
  status: 'active' | 'looted' | 'expiring' | 'contested';
  targetAsset: string;
  lootPayload: string;
}

interface BattleEvent {
  id: string;
  round: number;
  timestamp: string;
  leader: string;
  action: string;
  winner: string;
  scoreShift: string;
  details: string;
}

interface InfrastructureStatus {
  knowledge_hub_entries: number;
  egress_nodes: number;
  egress_current_ip: string;
  active_sessions: number;
}

export const ArenaView: React.FC = () => {
  const [round, setRound] = useState(1);
  const [shiftThreshold] = useState('连续 2 轮领先 30% 或 每 50 轮大洗牌');
  const [shuffleCountdown, setShuffleCountdown] = useState(50);
  const [simulating, setSimulating] = useState(false);
  const [autoSimulate, setAutoSimulate] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [combatModal, setCombatModal] = useState<any | null>(null);
  const [goalProb, setGoalProb] = useState(0.42);
  const [achievedNodes, setAchievedNodes] = useState<string[]>(['recon_info']);

  const [infra, setInfra] = useState<InfrastructureStatus>({
    knowledge_hub_entries: 5,
    egress_nodes: 3,
    egress_current_ip: '198.51.100.1',
    active_sessions: 2,
  });

  const [strategists, setStrategists] = useState<Strategist[]>([
    {
      id: 'claude-3-5-sonnet',
      name: 'Claude 3.5 Sonnet',
      model: 'claude-3-5-sonnet-20241022',
      avatarIcon: '🧠',
      avatarColor: 'from-purple-600 to-indigo-700 text-purple-200 border-purple-500/40',
      isLeader: true,
      score: 93.8,
      accuracy: 97.2,
      successRate: 89.5,
      riskReward: 94.7,
      wins: 24,
      totalRounds: 38,
      tacticalMode: 'Cairn 状态空间启发式搜索 + 意图图谱',
      equippedSkills: ['Linux提权自动化探测', 'SQL注入漏洞利用', 'Kerberoasting', 'JWT秘钥破解'],
      recentDecision: '推导最优攻破路径：利用 CVE-2024-38077 结合 LDAP 属性投毒实施突破。',
    },
    {
      id: 'deepseek-v3',
      name: 'DeepSeek-V3',
      model: 'deepseek-chat',
      avatarIcon: '⚡',
      avatarColor: 'from-blue-600 to-cyan-700 text-blue-200 border-blue-500/40',
      isLeader: false,
      score: 91.4,
      accuracy: 94.8,
      successRate: 92.1,
      riskReward: 87.3,
      wins: 19,
      totalRounds: 38,
      tacticalMode: '深度思维链 (CoT) 逆向推演',
      equippedSkills: ['EDR白名单绕过', '内存马无文件注入', 'AWS元数据渗出'],
      recentDecision: '提出规避 EDR 行为检测的内存注入 Payload，大幅降低触发告警概率。',
    },
    {
      id: 'gpt-4o',
      name: 'GPT-4o',
      model: 'gpt-4o',
      avatarIcon: '🎯',
      avatarColor: 'from-emerald-600 to-teal-700 text-emerald-200 border-emerald-500/40',
      isLeader: false,
      score: 87.9,
      accuracy: 89.4,
      successRate: 88.0,
      riskReward: 86.3,
      wins: 15,
      totalRounds: 38,
      tacticalMode: '广度并行探测 + 快速转化',
      equippedSkills: ['资产发现综合脚本', '子域名枚举爆破', 'Docker逃逸检查'],
      recentDecision: '并发枚举多分支路由与未授权接口，为战局提供广度指纹。',
    },
  ]);

  const [subagents, setSubagents] = useState<SubagentLoot[]>([
    {
      id: 'sub-01',
      code: '#Sub-Alpha',
      name: '漏洞验证探针 01',
      assignedTo: 'Claude 3.5 Sonnet',
      ttlRemaining: 180,
      status: 'active',
      targetAsset: '800211.com:443 (HTTPS)',
      lootPayload: '提取到 Admin Session Token & JWT 秘钥',
    },
    {
      id: 'sub-02',
      code: '#Sub-Beta',
      name: 'AD 域图谱爬虫 02',
      assignedTo: 'Claude 3.5 Sonnet',
      ttlRemaining: 125,
      status: 'active',
      targetAsset: 'dc01.corp.internal',
      lootPayload: '获取 Kerberos SPN 账号列表 (3 个特权服务)',
    },
    {
      id: 'sub-03',
      code: '#Sub-Gamma',
      name: '免杀载荷投放器 03',
      assignedTo: 'DeepSeek-V3',
      ttlRemaining: 85,
      status: 'looted',
      targetAsset: '192.168.1.200 (Database)',
      lootPayload: '被统帅成功调遣！获取数据库盲注通道',
    },
    {
      id: 'sub-04',
      code: '#Sub-Delta',
      name: '云元数据窥探器 04',
      assignedTo: 'GPT-4o',
      ttlRemaining: 40,
      status: 'expiring',
      targetAsset: '169.254.169.254 (IMDSv2)',
      lootPayload: '提取临时 IAM Role 凭证 (即将到期)',
    },
  ]);

  const [battleLogs, setBattleLogs] = useState<BattleEvent[]>([
    {
      id: 'log-1',
      round: 1,
      timestamp: '刚刚',
      leader: 'Claude 3.5 Sonnet',
      action: '边际贡献 ΔP 驱动 + 三维打分仲裁',
      winner: 'Claude 3.5',
      scoreShift: '初始统帅确立',
      details: '系统初始化完成，Claude 3.5 Sonnet 依据理论准确度与全局拓扑掌握战场最高统帅权。',
    },
  ]);

  // Synchronize equipped skills from localStorage
  useEffect(() => {
    const syncSkills = () => {
      try {
        const saved = localStorage.getItem('tiangong_equipped_skills');
        if (saved) {
          const parsed = JSON.parse(saved);
          if (parsed && typeof parsed === 'object') {
            setStrategists((prev) =>
              prev.map((s) => {
                if (s.id.includes('claude') && Array.isArray(parsed.claude)) {
                  return { ...s, equippedSkills: parsed.claude };
                }
                if (s.id.includes('deepseek') && Array.isArray(parsed.deepseek)) {
                  return { ...s, equippedSkills: parsed.deepseek };
                }
                if (s.id.includes('gpt') && Array.isArray(parsed.gpt)) {
                  return { ...s, equippedSkills: parsed.gpt };
                }
                return s;
              })
            );
          }
        }
      } catch (e) {}
    };

    syncSkills();
    window.addEventListener('tiangong_skills_updated', syncSkills);
    return () => window.removeEventListener('tiangong_skills_updated', syncSkills);
  }, []);

  // Handle updates from backend status payload
  const applyArenaData = (data: any) => {
    if (!data) return;
    if (typeof data.round === 'number') {
      setRound(data.round);
      setShuffleCountdown(Math.max(1, 50 - (data.round % 50)));
    }
    if (typeof data.auto_simulate === 'boolean') {
      setAutoSimulate(data.auto_simulate);
    }
    if (data.infrastructure) {
      setInfra(data.infrastructure);
    }
    if (data.graph) {
      if (typeof data.graph.goal_probability === 'number') {
        setGoalProb(data.graph.goal_probability);
      }
      if (Array.isArray(data.graph.achieved_nodes)) {
        setAchievedNodes(data.graph.achieved_nodes);
      }
    }
    if (data.ledger && Array.isArray(data.ledger.strategists)) {
      setStrategists((prev) =>
        prev.map((s) => {
          const live = data.ledger.strategists.find(
            (item: any) => item.id.includes(s.id) || s.id.includes(item.id)
          );
          if (!live) return s;
          return {
            ...s,
            score: live.recent_score || live.total_score || s.score,
            accuracy: live.accuracy || s.accuracy,
            successRate: live.success_rate || s.successRate,
            riskReward: live.risk_reward || s.riskReward,
            isLeader: Boolean(live.is_leader),
            wins: live.wins || s.wins,
            totalRounds: data.round || s.totalRounds,
          };
        })
      );
    }
    if (Array.isArray(data.recent_events) && data.recent_events.length > 0) {
      const latest = data.recent_events[data.recent_events.length - 1];
      const leaderName = latest.leader?.includes('claude')
        ? 'Claude 3.5 Sonnet'
        : latest.leader?.includes('deepseek')
        ? 'DeepSeek-V3'
        : 'GPT-4o';
      const logItem: BattleEvent = {
        id: `ev-${Date.now()}-${Math.random()}`,
        round: latest.round || data.round,
        timestamp: '实时流',
        leader: leaderName,
        action: latest.summary || latest.handover || latest.loot || '三维动态仲裁',
        winner: leaderName,
        scoreShift: `目标达成率: ${Math.round((latest.goal_prob || goalProb) * 100)}%`,
        details: latest.handover
          ? `【统帅权交接】${latest.handover}`
          : latest.loot
          ? `【子代理掠夺】${latest.loot}`
          : `第 ${latest.round} 轮推演完成，当前统帅为 ${leaderName}`,
      };
      setBattleLogs((prev) => [logItem, ...prev.slice(0, 6)]);
    }
  };

  // TTL Countdown ticker
  useEffect(() => {
    const timer = setInterval(() => {
      setSubagents((prev) =>
        prev.map((s) => ({
          ...s,
          ttlRemaining: Math.max(0, s.ttlRemaining - 1),
          status: s.ttlRemaining <= 1 ? 'expiring' : s.status,
        }))
      );
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Connect live SSE stream & initial status on mount
  useEffect(() => {
    getArenaStatus()
      .then(applyArenaData)
      .catch(() => {});

    const unsubscribe = subscribeArenaStream(
      (data) => applyArenaData(data),
      (err) => console.warn('Arena stream disconnected, fallback to normal', err)
    );
    return () => unsubscribe();
  }, []);

  const triggerRoundSimulation = async () => {
    setSimulating(true);
    try {
      const res = await simulateArenaRound();
      if (res && res.status) {
        applyArenaData(res.status);
        setToast(`第 ${res.status.round} 轮实时对抗裁决完成！`);
        setTimeout(() => setToast(null), 3000);
      }
    } catch (e: any) {
      setToast(`推演调用异常: ${e.message || String(e)}`);
      setTimeout(() => setToast(null), 3500);
    } finally {
      setSimulating(false);
    }
  };

  const handleToggleAutoSimulate = async () => {
    try {
      const next = !autoSimulate;
      const res = await toggleAutoSimulate(next);
      if (res && typeof res.auto_simulate === 'boolean') {
        setAutoSimulate(res.auto_simulate);
        setToast(res.auto_simulate ? '已开启自主连续博弈推演！' : '已暂停自主推演。');
        setTimeout(() => setToast(null), 3000);
      }
    } catch (e: any) {
      setToast(`切换自主推演失败: ${e.message || String(e)}`);
      setTimeout(() => setToast(null), 3500);
    }
  };

  const handleTacticalCombat = async (strategistId: string) => {
    try {
      setToast(`正在调遣战略家 ${strategistId} 消耗 50 积分下场肉搏...`);
      const res = await executeTacticalCombat(strategistId, 'foothold_access');
      if (res && res.combat_result) {
        const c = res.combat_result;
        setCombatModal(c);
        if (res.status) {
          applyArenaData(res.status);
        }
      }
    } catch (e: any) {
      setToast(`下场肉搏执行失败: ${e.message || String(e)}`);
      setTimeout(() => setToast(null), 3500);
    }
  };

  const currentLeader = strategists.find((s) => s.isLeader) || strategists[0];

  return (
    <div className="flex-1 p-5 md:p-6 overflow-y-auto text-slate-100 space-y-5 max-w-7xl mx-auto z-10 relative">
      {/* Toast */}
      {toast && (
        <div className="fixed top-5 right-5 z-50 px-4 py-3 bg-gradient-to-r from-purple-950/95 to-indigo-950/95 border border-purple-500/50 rounded-xl text-purple-200 text-xs font-medium flex items-center gap-2 shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-top-3">
          <Sparkles className="w-4 h-4 text-amber-400" />
          {toast}
        </div>
      )}

      {/* Tactical Combat Modal */}
      {combatModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-lg p-6 rounded-2xl bg-slate-900 border border-amber-500/60 shadow-2xl space-y-4 text-xs font-mono">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-amber-400 font-bold text-sm">
                <Crosshair className="w-5 h-5 text-amber-400 animate-spin" />
                战术肉搏突防战报 (Tactical Combat Report)
              </div>
              <button
                onClick={() => setCombatModal(null)}
                className="px-2 py-1 rounded bg-slate-800 text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">战略家:</span>
                <span className="text-purple-300 font-bold">{combatModal.strategist_id}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">消耗积分:</span>
                <span className="text-rose-400 font-bold">-{combatModal.points_cost} pts</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">突防战果:</span>
                <span className="text-emerald-400 font-bold">
                  {combatModal.success ? '防线击穿 (SUCCESS)' : '受阻'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">边际贡献 ΔP:</span>
                <span className="text-amber-300 font-bold">+{Math.round(combatModal.delta_p * 100)}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">赏金奖励:</span>
                <span className="text-cyan-300 font-bold">+{combatModal.reward_points} pts</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">统帅权更替:</span>
                <span className="text-amber-400 font-bold">
                  {combatModal.lead_captured ? '★ 夺取总指挥权' : '保持'}
                </span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1.5">
              <div className="text-[11px] text-slate-400 font-bold flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-cyan-400" />
                调取实时知识库 (RAG TKO) 战术参考:
              </div>
              {combatModal.knowledge_references?.map((ref: string, idx: number) => (
                <div key={idx} className="text-[10px] text-cyan-300 truncate">
                  • {ref}
                </div>
              ))}
            </div>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1 max-h-36 overflow-y-auto">
              <div className="text-[11px] text-slate-400 font-bold">突防执行日志:</div>
              {combatModal.action_log?.map((log: string, idx: number) => (
                <div key={idx} className="text-[11px] text-slate-300">
                  {log}
                </div>
              ))}
            </div>

            <button
              onClick={() => setCombatModal(null)}
              className="w-full py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold transition-all"
            >
              确认战报并返回战场
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-gradient-to-br from-amber-500/20 to-purple-500/20 border border-amber-500/40 text-amber-400">
              <Swords className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-black text-white tracking-tight">赛博战斗竞技场</h1>
                <span className="px-2 py-0.5 rounded-md bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-mono font-bold">
                  ROUND {round}
                </span>
                <span className="px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-mono font-bold">
                  ΔP 边际贡献驱动
                </span>
                <span className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-mono font-bold flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-ping" />
                  实时推流中
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                权力不是静态分配的，而是动态竞争出来的。基于理论准确度、执行成功率与风险收益比实时交接统帅权。
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={handleToggleAutoSimulate}
            className={`px-3.5 py-2 rounded-xl border text-xs font-bold font-mono transition-all flex items-center gap-1.5 shadow ${
              autoSimulate
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 hover:bg-rose-500/30'
                : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 hover:bg-emerald-500/30'
            }`}
          >
            {autoSimulate ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {autoSimulate ? '暂停自主推演' : '开启自主推演'}
          </button>

          <button
            onClick={triggerRoundSimulation}
            disabled={simulating}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 via-purple-600 to-indigo-600 hover:from-amber-400 hover:to-indigo-500 text-white text-xs font-bold transition-all shadow-lg shadow-purple-950/50 flex items-center gap-2 active:scale-95 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${simulating ? 'animate-spin' : ''}`} />
            {simulating ? '裁决推演中...' : '发起对抗推演'}
          </button>
        </div>
      </div>

      {/* Infrastructure Pillars Status Strip (三大实战基座) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div className="flex items-center gap-3 px-3 py-2 rounded-xl bg-slate-950/70 border border-slate-800/80">
          <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[10px] text-slate-400 font-mono">实时安全知识库 (RAG FTS5)</div>
            <div className="text-xs font-bold text-purple-300 font-mono">
              {infra.knowledge_hub_entries} 条现代绕过与利用规则在线
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 px-3 py-2 rounded-xl bg-slate-950/70 border border-slate-800/80">
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <Globe className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[10px] text-slate-400 font-mono">出口 IP 调度池 (Egress Manager)</div>
            <div className="text-xs font-bold text-cyan-300 font-mono">
              {infra.egress_current_ip} ({infra.egress_nodes} 个节点轮换 + 粘性会话)
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 px-3 py-2 rounded-xl bg-slate-950/70 border border-slate-800/80">
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Key className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[10px] text-slate-400 font-mono">长效会话维持池 (Session Vault)</div>
            <div className="text-xs font-bold text-emerald-300 font-mono">
              {infra.active_sessions} 组活跃凭证 (80% TTL 自动续签中)
            </div>
          </div>
        </div>
      </div>

      {/* Command Authority & Attack Graph Goal Progress Banner */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-purple-950/60 via-slate-900/90 to-indigo-950/60 border border-purple-500/40 shadow-xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 p-0.5 shadow-lg shadow-amber-500/20 flex items-center justify-center shrink-0">
              <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center text-2xl">
                <Crown className="w-7 h-7 text-amber-400 animate-pulse" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono uppercase tracking-wider text-amber-400 font-bold flex items-center gap-1">
                  <Flame className="w-3.5 h-3.5" /> 最高统帅 (Commanding Strategist)
                </span>
                <span className="text-[10px] font-mono px-2 py-0.2 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  综合分: {Math.round(currentLeader.score * 10) / 10}
                </span>
              </div>
              <h2 className="text-lg font-black text-white mt-0.5 flex items-center gap-2">
                {currentLeader.name}
                <span className="text-xs font-mono font-normal text-slate-400">({currentLeader.model})</span>
              </h2>
              <p className="text-xs text-slate-300 font-mono mt-1">
                掌握特权：决定主攻路径、调遣战术子智能体、支配 181 个实战武器库脚本与战利品分配。
              </p>
            </div>
          </div>

          {/* Goal Probability Gauge */}
          <div className="flex flex-col gap-2 bg-slate-950/70 p-3.5 rounded-xl border border-slate-800 shrink-0 min-w-[240px]">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400">攻破总目标概率 P(Goal):</span>
              <span className="font-bold text-amber-300">{Math.round(goalProb * 100)}%</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-purple-500 via-amber-400 to-emerald-400 h-full transition-all duration-500"
                style={{ width: `${Math.min(100, Math.round(goalProb * 100))}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
              <span>已达成节点: {achievedNodes.join(', ')}</span>
              <span>洗牌倒计时: {shuffleCountdown} 轮</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3 Scoring Dimensions Explanatory Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        <div className="p-4 rounded-xl bg-slate-900/80 border border-purple-500/30 shadow-md">
          <div className="flex items-center justify-between text-xs text-purple-400 font-bold mb-1">
            <span className="flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-purple-400" />
              维度一：理论准确度 (Theoretical Accuracy)
            </span>
            <span className="text-[10px] font-mono text-slate-400">想得对不对</span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            对当前攻击路径的逻辑推导是否符合安全原理、前置节点拓扑与协议规范。
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-cyan-500/30 shadow-md">
          <div className="flex items-center justify-between text-xs text-cyan-400 font-bold mb-1">
            <span className="flex items-center gap-1.5">
              <Activity className="w-4 h-4 text-cyan-400" />
              维度二：执行成功率 (Execution Success Rate)
            </span>
            <span className="text-[10px] font-mono text-slate-400">做得好不好</span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            提出的动作 (Action) 在目标靶机、网络探测与工具调用中的实际转化率与战果产出。
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-emerald-500/30 shadow-md">
          <div className="flex items-center justify-between text-xs text-emerald-400 font-bold mb-1">
            <span className="flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-emerald-400" />
              维度三：风险/收益比 (Risk/Reward Ratio)
            </span>
            <span className="text-[10px] font-mono text-slate-400">划不划算 (ΔP)</span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            在规避 EDR/WAF 防御与告警的同时，结合边际贡献 ΔP 以最低噪声获取最大的渗透收益。
          </p>
        </div>
      </div>

      {/* Strategist Roster Cards */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <Trophy className="w-4 h-4 text-amber-400" />
            策略官对抗天梯阵列 (Strategist Roster)
          </h3>
          <span className="text-xs text-slate-400 font-mono">多主脑实时博弈竞争</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {strategists.map((strat) => {
            return (
              <div
                key={strat.id}
                className={`p-5 rounded-2xl bg-slate-900/90 border transition-all relative flex flex-col justify-between shadow-lg ${
                  strat.isLeader
                    ? 'border-amber-500/60 shadow-amber-950/30 bg-slate-900/95 ring-1 ring-amber-500/40'
                    : 'border-slate-800 hover:border-slate-700'
                }`}
              >
                {strat.isLeader && (
                  <div className="absolute -top-3 right-4 px-2.5 py-0.5 rounded-full bg-amber-500 text-slate-950 font-black text-[10px] font-mono shadow flex items-center gap-1">
                    <Crown className="w-3 h-3" /> 统帅执掌中
                  </div>
                )}

                <div>
                  {/* Top Avatar & Name */}
                  <div className="flex items-center gap-3 mb-3.5">
                    <div
                      className={`w-11 h-11 rounded-xl bg-gradient-to-br ${strat.avatarColor} p-0.5 flex items-center justify-center text-xl shadow-md`}
                    >
                      <div className="w-full h-full bg-slate-950/80 rounded-[10px] flex items-center justify-center">
                        {strat.avatarIcon}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-white">{strat.name}</h4>
                      <p className="text-[10px] font-mono text-slate-400">{strat.model}</p>
                    </div>
                  </div>

                  {/* Total Score Badge */}
                  <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 mb-3.5">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-slate-400 font-mono">综合竞技评分</span>
                      <span className="text-lg font-black font-mono text-amber-300">
                        {Math.round(strat.score * 10) / 10}
                      </span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-purple-500 via-amber-400 to-emerald-400 h-full transition-all duration-500"
                        style={{ width: `${Math.min(100, strat.score)}%` }}
                      />
                    </div>
                  </div>

                  {/* 3 Dimensions Breakdown */}
                  <div className="space-y-2 text-xs font-mono mb-3.5">
                    <div className="flex items-center justify-between">
                      <span className="text-purple-300/90 text-[11px]">理论准确度</span>
                      <span className="text-purple-300 font-bold">{Math.round(strat.accuracy)}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-cyan-300/90 text-[11px]">执行成功率</span>
                      <span className="text-cyan-300 font-bold">{Math.round(strat.successRate)}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-emerald-300/90 text-[11px]">风险/收益比</span>
                      <span className="text-emerald-300 font-bold">{Math.round(strat.riskReward)}%</span>
                    </div>
                  </div>

                  {/* Tactical Mode */}
                  <div className="p-2.5 rounded-lg bg-slate-950/50 border border-slate-800/60 mb-3">
                    <div className="text-[10px] font-mono text-slate-500 uppercase">战术决策模式</div>
                    <div className="text-xs font-medium text-slate-300 mt-0.5 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                      <span className="truncate">{strat.tacticalMode}</span>
                    </div>
                  </div>

                  {/* Equipped Skills list */}
                  <div className="mb-3">
                    <div className="text-[10px] font-mono text-slate-500 uppercase mb-1">
                      装配武器与技能 ({strat.equippedSkills.length})
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {strat.equippedSkills.map((sk) => (
                        <span
                          key={sk}
                          className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800/90 text-slate-300 border border-slate-700/60"
                        >
                          {sk}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Tactical Combat Button ("亲自下场") */}
                <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between">
                  <div className="text-[11px] text-slate-400 font-mono">
                    胜场: <span className="text-amber-300 font-bold">{strat.wins}</span>
                  </div>
                  <button
                    onClick={() => handleTacticalCombat(strat.id)}
                    className="px-2.5 py-1 rounded-lg bg-gradient-to-r from-amber-600 to-rose-600 hover:from-amber-500 hover:to-rose-500 text-white text-[11px] font-bold font-mono transition-all flex items-center gap-1 shadow active:scale-95"
                  >
                    <Crosshair className="w-3 h-3" />
                    亲自下场 (-50 pts)
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Subagent Looting & Battle Log Strip */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Subagent Roster */}
        <div className="p-5 rounded-2xl bg-slate-900/85 border border-slate-800 shadow-md space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Skull className="w-4 h-4 text-rose-400" />
              战术子智能体分配与劫持 (Subagent Looting)
            </h3>
            <span className="text-[11px] font-mono text-slate-400">生存周期 (TTL) 机制</span>
          </div>
          <p className="text-xs text-slate-400">
            高分统帅可对落后模型的子智能体发起掠夺（Loot），夺取其探测成果并继承存活 TTL。
          </p>

          <div className="space-y-2.5">
            {subagents.map((sub) => {
              return (
                <div
                  key={sub.id}
                  className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center justify-between gap-3 text-xs"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-amber-300">{sub.code}</span>
                      <span className="font-medium text-slate-200">{sub.name}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400">
                        归属: {sub.assignedTo}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono truncate">
                      🎯 {sub.targetAsset} · {sub.lootPayload}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right font-mono">
                      <div className="text-[10px] text-slate-500">TTL 倒计时</div>
                      <div
                        className={`text-xs font-bold flex items-center gap-1 ${
                          sub.ttlRemaining < 30 ? 'text-rose-400 animate-pulse' : 'text-cyan-300'
                        }`}
                      >
                        <Clock className="w-3 h-3" />
                        {sub.ttlRemaining}s
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Live Battle & Power Shift Log */}
        <div className="p-5 rounded-2xl bg-slate-900/85 border border-slate-800 shadow-md space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              对抗与权力转移实时日志 (Battle Log)
            </h3>
            <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-ping" />
              LIVE
            </span>
          </div>

          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {battleLogs.map((log) => (
              <div
                key={log.id}
                className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1 text-xs font-mono"
              >
                <div className="flex items-center justify-between text-slate-400 text-[11px]">
                  <span className="text-amber-300 font-bold">第 {log.round} 轮推演</span>
                  <span>{log.timestamp}</span>
                </div>
                <div className="text-slate-200 font-semibold flex items-center gap-1.5">
                  <span className="text-purple-400">{log.leader}</span>
                  <span className="text-slate-500">→</span>
                  <span className="text-emerald-300">{log.winner}</span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">{log.details}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
