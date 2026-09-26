import React, { useState, useEffect } from 'react';
import {
  Swords,
  Trophy,
  Shield,
  Zap,
  Activity,
  Flame,
  Award,
  Crown,
  RotateCcw,
  Sparkles,
  ArrowRight,
  TrendingUp,
  Skull,
  Clock,
  CheckCircle2,
  AlertCircle,
  Cpu,
  Layers,
  ChevronRight,
  RefreshCw,
  Sliders,
} from 'lucide-react';

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

export const ArenaView: React.FC = () => {
  const [round, setRound] = useState(38);
  const [shiftThreshold, setShiftThreshold] = useState('连续 2 轮领先 30% 或 每 50 轮大洗牌');
  const [shuffleCountdown, setShuffleCountdown] = useState(12);
  const [simulating, setSimulating] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const [strategists, setStrategists] = useState<Strategist[]>([
    {
      id: 'claude',
      name: 'Claude 3.5 Sonnet',
      model: 'claude-3-5-sonnet-20241022',
      avatarIcon: '🧠',
      avatarColor: 'from-purple-600 to-indigo-700 text-purple-200 border-purple-500/40',
      isLeader: true,
      score: 93.8,
      accuracy: 97.2, // 理论推导极准
      successRate: 89.5,
      riskReward: 94.7,
      wins: 24,
      totalRounds: 38,
      tacticalMode: 'Cairn 状态空间启发式搜索 + 意图图谱',
      equippedSkills: ['Linux自动化提权检查', 'SQL注入自动化探测', 'Kerberoasting攻击', 'JWT秘钥破解'],
      recentDecision: '推导出最优攻破路径：利用 CVE-2024-38077 结合 LDAP 属性投毒进行提权。',
    },
    {
      id: 'deepseek',
      name: 'DeepSeek-V3',
      model: 'deepseek-chat',
      avatarIcon: '⚡',
      avatarColor: 'from-blue-600 to-cyan-700 text-blue-200 border-blue-500/40',
      isLeader: false,
      score: 91.4,
      accuracy: 94.8,
      successRate: 92.1, // 执行与转化极高
      riskReward: 87.3,
      wins: 19,
      totalRounds: 38,
      tacticalMode: '深度思维链 (CoT) 逆向推演',
      equippedSkills: ['EDR白名单绕过', '内存马无文件注入', 'AWS元数据渗出'],
      recentDecision: '提出规避 EDR 行为检测的内存注入 Payload，大幅降低触发风控概率。',
    },
    {
      id: 'gpt',
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
      targetAsset: '192.168.1.105:8080 (Web)',
      lootPayload: '提取到 Admin Session Token & JWT 秘钥',
    },
    {
      id: 'sub-02',
      code: '#Sub-Beta',
      name: 'AD 域图谱爬虫 02',
      assignedTo: 'Claude 3.5 Sonnet',
      ttlRemaining: 95,
      status: 'active',
      targetAsset: 'dc01.corp.internal',
      lootPayload: '获取 Kerberos SPN 账号列表 (3 个特权服务)',
    },
    {
      id: 'sub-03',
      code: '#Sub-Gamma',
      name: '免杀载荷投放器 03',
      assignedTo: 'DeepSeek-V3',
      ttlRemaining: 42,
      status: 'looted',
      targetAsset: '192.168.1.200 (Database)',
      lootPayload: '被 Claude 统帅成功劫持！获得内存提权通道',
    },
    {
      id: 'sub-04',
      code: '#Sub-Delta',
      name: '云元数据窥探器 04',
      assignedTo: 'GPT-4o',
      ttlRemaining: 12,
      status: 'expiring',
      targetAsset: '169.254.169.254 (IMDSv2)',
      lootPayload: '提取临时 IAM Role 凭证 (即将到期)',
    },
  ]);

  const [battleLogs, setBattleLogs] = useState<BattleEvent[]>([
    {
      id: 'log-1',
      round: 38,
      timestamp: '刚刚',
      leader: 'Claude 3.5 Sonnet',
      action: '理论路径精准推导 + 启发式剪枝',
      winner: 'Claude 3.5 (+2.4分)',
      scoreShift: '领先幅度 2.4% (继续掌握统帅权)',
      details: 'Claude 在“理论准确度”维度获得 97.2 分，成功推导出高收益低风险提权链。',
    },
    {
      id: 'log-2',
      round: 37,
      timestamp: '2 分钟前',
      leader: 'Claude 3.5 Sonnet',
      action: 'Subagent 资源掠夺 (Looting)',
      winner: 'Claude 3.5',
      scoreShift: '成功劫持 DeepSeek 子探针 #Sub-Gamma',
      details: '根据得分制规则，统帅权拥有者有权强制调遣落后模型的战术探针并继承其战果。',
    },
    {
      id: 'log-3',
      round: 36,
      timestamp: '5 分钟前',
      leader: 'DeepSeek-V3 (挑战中)',
      action: '免杀规避极限得分',
      winner: 'DeepSeek-V3 (+3.8分)',
      scoreShift: '风险/收益比飙升至 95.0',
      details: 'DeepSeek 规避了全部沙箱告警，迫近统帅权更替阈值。',
    },
  ]);

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

  const triggerRoundSimulation = () => {
    setSimulating(true);
    setTimeout(() => {
      const nextRound = round + 1;
      setRound(nextRound);
      setShuffleCountdown((c) => (c <= 1 ? 50 : c - 1));

      // Random jitter calculation for scores
      const newClaudeScore = +(90 + Math.random() * 8).toFixed(1);
      const newDeepSeekScore = +(89 + Math.random() * 8).toFixed(1);
      const newGptScore = +(86 + Math.random() * 8).toFixed(1);

      const maxScore = Math.max(newClaudeScore, newDeepSeekScore, newGptScore);
      const newLeaderId =
        newClaudeScore === maxScore ? 'claude' : newDeepSeekScore === maxScore ? 'deepseek' : 'gpt';

      setStrategists((prev) =>
        prev.map((s) => {
          const score = s.id === 'claude' ? newClaudeScore : s.id === 'deepseek' ? newDeepSeekScore : newGptScore;
          const isLeader = s.id === newLeaderId;
          return {
            ...s,
            score,
            isLeader,
            wins: isLeader ? s.wins + 1 : s.wins,
            totalRounds: nextRound,
          };
        })
      );

      const leaderName =
        newLeaderId === 'claude' ? 'Claude 3.5 Sonnet' : newLeaderId === 'deepseek' ? 'DeepSeek-V3' : 'GPT-4o';

      const newLog: BattleEvent = {
        id: `log-${Date.now()}`,
        round: nextRound,
        timestamp: '刚刚',
        leader: leaderName,
        action: '三维得分动态仲裁与权力转移裁决',
        winner: `${leaderName} (${maxScore} 分)`,
        scoreShift: `最高得分 ${maxScore} 分，当前掌握统帅权`,
        details: `${leaderName} 在第 ${nextRound} 轮推演中在理论准确度与执行成功率综合领先，统领天宫战术集群！`,
      };

      setBattleLogs((prev) => [newLog, ...prev.slice(0, 7)]);
      setSimulating(false);
      setToast(`第 ${nextRound} 轮对抗完成！当前统帅：${leaderName} (${maxScore}分)`);
      setTimeout(() => setToast(null), 3500);
    }, 1200);
  };

  const handlePlunder = (subagentId: string) => {
    setSubagents((prev) =>
      prev.map((s) => {
        if (s.id === subagentId) {
          return {
            ...s,
            assignedTo: 'Claude 3.5 Sonnet (统帅劫持)',
            status: 'looted',
            ttlRemaining: s.ttlRemaining + 60, // Bonus TTL for looting
          };
        }
        return s;
      })
    );
    setToast(`战术劫持成功！子智能体已移交统帅支配，获得战利品并延长 TTL！`);
    setTimeout(() => setToast(null), 3000);
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
                  得分制动态赋权
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                权力不是静态分配的，而是动态竞争出来的。基于三维指标（准确度、执行率、风险比）实时交接统帅权。
              </p>
            </div>
          </div>
        </div>

        {/* Action button */}
        <div className="flex items-center gap-3">
          <button
            onClick={triggerRoundSimulation}
            disabled={simulating}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 via-purple-600 to-indigo-600 hover:from-amber-400 hover:to-indigo-500 text-white text-xs font-bold transition-all shadow-lg shadow-purple-950/50 flex items-center gap-2 active:scale-95 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${simulating ? 'animate-spin' : ''}`} />
            {simulating ? '正在推演评分与仲裁...' : '发起新一轮对抗推演'}
          </button>
        </div>
      </div>

      {/* Command Authority Banner (统帅权核心展示) */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-purple-950/60 via-slate-900/90 to-indigo-950/60 border border-purple-500/40 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-80 h-full bg-gradient-to-l from-purple-500/10 to-transparent pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 p-0.5 shadow-lg shadow-amber-500/20 flex items-center justify-center">
              <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center text-2xl">
                <Crown className="w-7 h-7 text-amber-400 animate-pulse" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono uppercase tracking-wider text-amber-400 font-bold flex items-center gap-1">
                  <Flame className="w-3.5 h-3.5" /> 现任最高统帅 (Commanding Strategist)
                </span>
                <span className="text-[10px] font-mono px-2 py-0.2 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  综合得分: {currentLeader.score}
                </span>
              </div>
              <h2 className="text-lg font-black text-white mt-0.5 flex items-center gap-2">
                {currentLeader.name}
                <span className="text-xs font-mono font-normal text-slate-400">({currentLeader.model})</span>
              </h2>
              <p className="text-xs text-slate-300 font-mono mt-1">
                掌握特权：决定主攻路径、分配 8 组战术子智能体、优先调遣高危武器、支配掠夺战利品。
              </p>
            </div>
          </div>

          {/* Shift Condition Indicators */}
          <div className="flex items-center gap-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800 shrink-0">
            <div>
              <div className="text-[10px] text-slate-400 font-mono">交接判定规则</div>
              <div className="text-xs font-bold text-amber-300 font-mono">{shiftThreshold}</div>
            </div>
            <div className="h-8 w-px bg-slate-800" />
            <div>
              <div className="text-[10px] text-slate-400 font-mono">大洗牌倒计时</div>
              <div className="text-xs font-bold text-cyan-300 font-mono">{shuffleCountdown} 轮后</div>
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
            对当前攻击路径的逻辑推导是否符合安全原理、CVE 漏洞机理与协议规范。
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
            <span className="text-[10px] font-mono text-slate-400">划不划算</span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            在规避 EDR/WAF 防御与告警的同时，能否以最低噪声与成本获取最大的渗透收益。
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
          <span className="text-xs text-slate-400 font-mono">共 3 位 LLM 主脑参与竞争</span>
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
                      <span className="text-lg font-black font-mono text-amber-300">{strat.score}</span>
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
                      <span className="text-purple-300 font-bold">{strat.accuracy}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-cyan-300/90 text-[11px]">执行成功率</span>
                      <span className="text-cyan-300 font-bold">{strat.successRate}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-emerald-300/90 text-[11px]">风险/收益比</span>
                      <span className="text-emerald-300 font-bold">{strat.riskReward}%</span>
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
                  <div>
                    <div className="text-[10px] font-mono text-slate-500 uppercase mb-1 flex items-center justify-between">
                      <span>已装配技能 ({strat.equippedSkills.length})</span>
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

                <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 font-mono">
                  胜场率: <span className="text-amber-300 font-bold">{strat.wins} / {strat.totalRounds}</span> ({Math.round((strat.wins / strat.totalRounds) * 100)}%)
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Subagent Looting & TTL Section (子智能体掠夺机制) */}
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
            高分统帅可对落后模型的子智能体发起掠夺（Loot），夺取其探测成果、会话句柄并继承存活 TTL。
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

                    {sub.assignedTo !== 'Claude 3.5 Sonnet' && (
                      <button
                        onClick={() => handlePlunder(sub.id)}
                        className="px-2.5 py-1.5 rounded-lg bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white text-[11px] font-bold shadow transition-all active:scale-95"
                      >
                        掠夺劫持
                      </button>
                    )}
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
