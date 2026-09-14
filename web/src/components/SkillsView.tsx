import React, { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  Shield,
  Zap,
  Terminal,
  CheckCircle2,
  Copy,
  ExternalLink,
  Cpu,
  Layers,
  Sparkles,
  ChevronRight,
  Award,
  Play,
  Check,
  Flame,
  Code,
  AlertTriangle,
  FolderCode,
} from 'lucide-react';
import rawSkillsData from '../skills_data.json';

interface SkillItem {
  id: string;
  name: string;
  category: string;
  category_en?: string;
  icon?: string;
  desc?: string;
  path?: string;
  script_count?: number;
  tags?: string[];
  scripts?: string[];
  risk?: string;
  content_preview?: string;
}

// Extract categories dynamically from skills_data.json
const rawCategories = (rawSkillsData as any).categories || {};
const CATEGORY_MAP: Record<string, { en: string; icon: string; desc: string }> = {
  '全部': { en: 'all', icon: '⚔️', desc: '全量 181 项网络战斗实战技能武器' },
  ...rawCategories,
};

// Flatten skills from json root array
function parseSkills(): SkillItem[] {
  const raw = rawSkillsData as any;
  if (!raw) return [];
  const list = Array.isArray(raw.skills) ? raw.skills : [];
  
  return list.map((skill: any, index: number) => {
    const scriptsList = Array.isArray(skill.scripts)
      ? skill.scripts.map((s: any) => (typeof s === 'string' ? s : s.filename || 'script.py'))
      : ['script.py'];

    const riskLevel = skill.category?.includes('利用')
      ? 'HIGH'
      : skill.category?.includes('提权')
      ? 'CRITICAL'
      : skill.category?.includes('免杀')
      ? 'HIGH'
      : skill.category?.includes('云平台')
      ? 'HIGH'
      : 'MEDIUM';

    return {
      id: skill.id || `skill-${index}`,
      name: skill.name || '未命名技能',
      category: skill.category || '未分类',
      category_en: skill.category_en,
      icon: skill.category_icon || rawCategories[skill.category]?.icon || '⚔️',
      desc: skill.description || rawCategories[skill.category]?.desc || '网络安全实战自动化执行技能',
      path: skill.path || '',
      script_count: scriptsList.length,
      tags: skill.trigger_words || [skill.category, skill.category_en || 'security'],
      scripts: scriptsList,
      risk: riskLevel,
      content_preview: `# 实战技能自动化执行脚本: ${skill.name}
# 所属分类: ${skill.category} (${skill.category_en || 'sec'})
# 武器库物理路径: ${skill.path}
# 包含脚本: ${scriptsList.join(', ')}

import sys
import os

def run_exploit(target_host, options=None):
    """
    【${skill.name}】战术动作执行入口
    已装备至天宫战术决策引擎，支持策略官(Claude/GPT/DeepSeek)实时调度
    """
    print(f"[+] 正在向目标执行 ${skill.name}: {target_host}")
    # 自动化探测与利用链逻辑
    return {
        "status": "SUCCESS",
        "skill_id": "${skill.id}",
        "executed_script": "${scriptsList[0] || 'script.py'}",
        "evidence": "Exploit sequence executed cleanly"
    }

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    run_exploit(target)
`,
    };
  });
}

const LOCAL_STORAGE_KEY = 'tiangong_equipped_skills';

const DEFAULT_EQUIPPED: Record<string, string[]> = {
  claude: ['Capabilities与特殊权限', 'Sudo与SUID提权', 'Kerberos攻击', 'SQL注入全自动挖掘'],
  gpt: ['Docker与容器逃逸', 'AWS元数据渗透与提权', '子域名深度枚举爆破'],
  deepseek: ['EDR白名单绕过', '内存马无文件注入', 'Linux内核提权自动化'],
};

export const SkillsView: React.FC<{
  onEquip?: (strategistId: string, skillId: string) => void;
}> = ({ onEquip }) => {
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('全部');
  const [selectedSkill, setSelectedSkill] = useState<SkillItem | null>(null);
  const [equippedSkills, setEquippedSkills] = useState<Record<string, string[]>>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && typeof parsed === 'object') {
          return {
            claude: Array.isArray(parsed.claude) ? parsed.claude : [],
            gpt: Array.isArray(parsed.gpt) ? parsed.gpt : [],
            deepseek: Array.isArray(parsed.deepseek) ? parsed.deepseek : [],
          };
        }
      }
    } catch (e) {
      console.warn('Failed to load equipped skills from localStorage:', e);
    }
    return DEFAULT_EQUIPPED;
  });
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const allSkills = useMemo(() => parseSkills(), []);

  const filteredSkills = useMemo(() => {
    return allSkills.filter((s) => {
      const matchCat = selectedCategory === '全部' || s.category === selectedCategory;
      const matchSearch =
        !search ||
        s.name.toLowerCase().includes(search.toLowerCase()) ||
        s.desc?.toLowerCase().includes(search.toLowerCase()) ||
        s.category.toLowerCase().includes(search.toLowerCase()) ||
        (s.category_en && s.category_en.toLowerCase().includes(search.toLowerCase()));
      return matchCat && matchSearch;
    });
  }, [allSkills, selectedCategory, search]);

  const saveEquipped = (next: Record<string, string[]>) => {
    setEquippedSkills(next);
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(next));
      window.dispatchEvent(new Event('tiangong_skills_updated'));
    } catch (e) {}
  };

  // Equip single skill to one strategist
  const handleEquip = (strategistId: string, skill: SkillItem) => {
    const current = equippedSkills[strategistId] || [];
    if (current.includes(skill.name)) {
      setToast(`策略官已装配过「${skill.name}」`);
      setTimeout(() => setToast(null), 2000);
      return;
    }
    const next = {
      ...equippedSkills,
      [strategistId]: [...current, skill.name],
    };
    saveEquipped(next);
    const stratName = strategistId === 'claude' ? 'Claude 3.5' : strategistId === 'gpt' ? 'GPT-4o' : 'DeepSeek-V3';
    setToast(`已将「${skill.name}」装备至策略官 ${stratName}`);
    setTimeout(() => setToast(null), 3000);
    if (onEquip) {
      onEquip(strategistId, skill.id);
    }
  };

  // Equip single skill to all 3 strategists
  const handleEquipSkillToAll = (skill: SkillItem) => {
    const next = {
      claude: Array.from(new Set([...(equippedSkills.claude || []), skill.name])),
      gpt: Array.from(new Set([...(equippedSkills.gpt || []), skill.name])),
      deepseek: Array.from(new Set([...(equippedSkills.deepseek || []), skill.name])),
    };
    saveEquipped(next);
    setToast(`⚡ 已将「${skill.name}」一键装备至全员策略官 (Claude + GPT-4o + DeepSeek)！`);
    setTimeout(() => setToast(null), 3000);
    if (onEquip) {
      onEquip('all', skill.id);
    }
  };

  // 一键全员全量装配 (181项全部装配给全部谋士)
  const handleEquipAllFleets = () => {
    const allNames = allSkills.map((s) => s.name);
    const next = {
      claude: Array.from(new Set([...(equippedSkills.claude || []), ...allNames])),
      gpt: Array.from(new Set([...(equippedSkills.gpt || []), ...allNames])),
      deepseek: Array.from(new Set([...(equippedSkills.deepseek || []), ...allNames])),
    };
    saveEquipped(next);
    setToast(`🚀 战术武装完成！已将全部 ${allSkills.length} 项实战技能一键全量装配至三大策略官！`);
    setTimeout(() => setToast(null), 4000);
  };

  // 一键装配当前分类 (当前选中的分类或者搜索结果) 给全员
  const handleEquipCurrentCategoryToAll = () => {
    const targetSkills = filteredSkills.map((s) => s.name);
    if (targetSkills.length === 0) return;
    const next = {
      claude: Array.from(new Set([...(equippedSkills.claude || []), ...targetSkills])),
      gpt: Array.from(new Set([...(equippedSkills.gpt || []), ...targetSkills])),
      deepseek: Array.from(new Set([...(equippedSkills.deepseek || []), ...targetSkills])),
    };
    saveEquipped(next);
    setToast(`🎯 已将当前「${selectedCategory}」分类下 ${targetSkills.length} 项技能一键装备至全员策略官！`);
    setTimeout(() => setToast(null), 3500);
  };

  // 一键装配全部或当前分类给指定策略官
  const handleEquipAllToStrategist = (stratId: string, useCurrentFiltered: boolean = false) => {
    const pool = useCurrentFiltered ? filteredSkills : allSkills;
    const names = pool.map((s) => s.name);
    const stratName = stratId === 'claude' ? 'Claude 3.5' : stratId === 'gpt' ? 'GPT-4o' : 'DeepSeek-V3';
    const next = {
      ...equippedSkills,
      [stratId]: Array.from(new Set([...(equippedSkills[stratId] || []), ...names])),
    };
    saveEquipped(next);
    setToast(`⚔️ 已将 ${useCurrentFiltered ? `「${selectedCategory}」${names.length}项` : `全部 ${names.length}项`}技能装备至 ${stratName}！`);
    setTimeout(() => setToast(null), 3500);
  };

  // 清空指定谋士
  const handleClearStrategist = (stratId: string) => {
    const stratName = stratId === 'claude' ? 'Claude 3.5' : stratId === 'gpt' ? 'GPT-4o' : 'DeepSeek-V3';
    const next = {
      ...equippedSkills,
      [stratId]: [],
    };
    saveEquipped(next);
    setToast(`已清空 ${stratName} 的装配技能`);
    setTimeout(() => setToast(null), 2500);
  };

  // 重置回默认
  const handleResetDefaults = () => {
    saveEquipped(DEFAULT_EQUIPPED);
    setToast('已恢复系统默认技能装配状态');
    setTimeout(() => setToast(null), 2500);
  };

  const claudeCount = equippedSkills.claude?.length || 0;
  const gptCount = equippedSkills.gpt?.length || 0;
  const deepseekCount = equippedSkills.deepseek?.length || 0;
  const isAllFullyEquipped =
    allSkills.length > 0 &&
    claudeCount >= allSkills.length &&
    gptCount >= allSkills.length &&
    deepseekCount >= allSkills.length;

  const copyCode = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex-1 p-5 md:p-6 overflow-y-auto text-slate-100 space-y-5 max-w-7xl mx-auto z-10 relative">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed top-5 right-5 z-50 px-4 py-3 bg-cyan-950/95 border border-cyan-500/50 rounded-xl text-cyan-200 text-xs font-medium flex items-center gap-2 shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-top-3">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          {toast}
        </div>
      )}

      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-black text-white tracking-tight">实战技能武器库</h1>
                <span className="px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-mono font-bold">
                  {allSkills.length} SKILLS
                </span>
                <span className="px-2 py-0.5 rounded-md bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-mono font-bold">
                  {Object.keys(CATEGORY_MAP).length - 1} 分类
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                覆盖 Web、内网 AD、Linux 提权、云安全、免杀规避与智能体协同全战术链路，可实时赋能策略官。
              </p>
            </div>
          </div>
        </div>

        {/* Search Bar */}
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索 181 项实战技能或关键词..."
            className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/60 focus:ring-1 focus:ring-amber-500/30 transition-all font-mono"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 text-xs"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* 【一键全加 / 战术武装控制中枢】 */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/95 to-slate-950 border border-amber-500/30 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-full bg-gradient-to-l from-amber-500/10 via-cyan-500/5 to-transparent pointer-events-none" />

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 relative z-10">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs">
                ⚡ 战备装配指令
              </span>
              <h2 className="text-sm font-bold text-white tracking-wide">
                策略官实战技能一键全量装配中枢
              </h2>
              <span className="text-[11px] font-mono text-slate-400">
                (已装填总槽位: <span className="text-amber-300 font-bold">{claudeCount + gptCount + deepseekCount}</span> / {allSkills.length * 3})
              </span>
            </div>
            <p className="text-xs text-slate-400">
              支持全员一键拉满、当前分类一键加装或按谋士分流配装，配置状态全端自动持久化保存。
            </p>
          </div>

          {/* Action Button Group */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Primary 一键全加 Button */}
            <button
              onClick={handleEquipAllFleets}
              disabled={isAllFullyEquipped}
              className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-all shadow-lg ${
                isAllFullyEquipped
                  ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-500/40 cursor-default'
                  : 'bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black shadow-amber-500/20 hover:scale-[1.02] active:scale-[0.98]'
              }`}
            >
              {isAllFullyEquipped ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>全员已全量拉满 (181/181)</span>
                </>
              ) : (
                <>
                  <Flame className="w-4 h-4 text-slate-950 animate-pulse" />
                  <span>⚡ 一键全员全量装配 (181项拉满)</span>
                </>
              )}
            </button>

            {/* 一键装配当前分类 Button */}
            {selectedCategory !== '全部' && (
              <button
                onClick={handleEquipCurrentCategoryToAll}
                className="px-3.5 py-2 rounded-xl bg-cyan-950/70 hover:bg-cyan-900/80 border border-cyan-500/40 text-cyan-300 text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm shadow-cyan-950/50 hover:scale-[1.02]"
              >
                <Zap className="w-3.5 h-3.5 text-cyan-400" />
                <span>一键装配当前分类 ({filteredSkills.length}项)</span>
              </button>
            )}

            {/* Quick Strategic Equip Drops */}
            <div className="flex items-center gap-1 bg-slate-950/80 p-1 rounded-xl border border-slate-800">
              <button
                onClick={() => handleEquipAllToStrategist('claude', false)}
                title="将全量 181 项技能装备给 Claude 3.5"
                className="px-2.5 py-1.5 rounded-lg bg-purple-950/40 hover:bg-purple-900/60 border border-purple-500/30 text-purple-300 text-xs font-mono font-medium transition-colors"
              >
                + Claude全加
              </button>
              <button
                onClick={() => handleEquipAllToStrategist('gpt', false)}
                title="将全量 181 项技能装备给 GPT-4o"
                className="px-2.5 py-1.5 rounded-lg bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-500/30 text-emerald-300 text-xs font-mono font-medium transition-colors"
              >
                + GPT全加
              </button>
              <button
                onClick={() => handleEquipAllToStrategist('deepseek', false)}
                title="将全量 181 项技能装备给 DeepSeek-V3"
                className="px-2.5 py-1.5 rounded-lg bg-blue-950/40 hover:bg-blue-900/60 border border-blue-500/30 text-blue-300 text-xs font-mono font-medium transition-colors"
              >
                + DeepSeek全加
              </button>
              <button
                onClick={handleResetDefaults}
                title="重置装配为系统默认状态"
                className="px-2 py-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 text-xs transition-colors"
              >
                重置
              </button>
            </div>
          </div>
        </div>

        {/* 策略官战备装甲仪表板 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3.5 pt-3.5 border-t border-slate-800/80">
          {/* Claude */}
          <div className="p-2.5 rounded-xl bg-slate-950/70 border border-purple-500/20 flex flex-col justify-between gap-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-purple-400" />
                <span className="text-xs font-bold text-purple-200">Claude 3.5 Sonnet</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-mono text-purple-300 font-bold">
                  {claudeCount} / {allSkills.length}
                </span>
                {claudeCount > 0 && (
                  <button
                    onClick={() => handleClearStrategist('claude')}
                    className="text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
                  >
                    清空
                  </button>
                )}
              </div>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-gradient-to-r from-purple-500 to-indigo-500 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, Math.round((claudeCount / (allSkills.length || 1)) * 100))}%` }}
              />
            </div>
          </div>

          {/* GPT-4o */}
          <div className="p-2.5 rounded-xl bg-slate-950/70 border border-emerald-500/20 flex flex-col justify-between gap-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="text-xs font-bold text-emerald-200">GPT-4o 战术官</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-mono text-emerald-300 font-bold">
                  {gptCount} / {allSkills.length}
                </span>
                {gptCount > 0 && (
                  <button
                    onClick={() => handleClearStrategist('gpt')}
                    className="text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
                  >
                    清空
                  </button>
                )}
              </div>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-gradient-to-r from-emerald-500 to-teal-500 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, Math.round((gptCount / (allSkills.length || 1)) * 100))}%` }}
              />
            </div>
          </div>

          {/* DeepSeek-V3 */}
          <div className="p-2.5 rounded-xl bg-slate-950/70 border border-blue-500/20 flex flex-col justify-between gap-1.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-400" />
                <span className="text-xs font-bold text-blue-200">DeepSeek-V3 推理官</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-mono text-blue-300 font-bold">
                  {deepseekCount} / {allSkills.length}
                </span>
                {deepseekCount > 0 && (
                  <button
                    onClick={() => handleClearStrategist('deepseek')}
                    className="text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
                  >
                    清空
                  </button>
                )}
              </div>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-gradient-to-r from-blue-500 to-cyan-500 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, Math.round((deepseekCount / (allSkills.length || 1)) * 100))}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Category Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1.5 scrollbar-thin">
        {Object.entries(CATEGORY_MAP).map(([catName, catInfo]) => {
          const active = selectedCategory === catName;
          const count = catName === '全部' ? allSkills.length : allSkills.filter((s) => s.category === catName).length;
          return (
            <button
              key={catName}
              onClick={() => setSelectedCategory(catName)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-all flex items-center gap-1.5 border ${
                active
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm shadow-amber-950/50'
                  : 'bg-slate-900/70 text-slate-400 border-slate-800 hover:bg-slate-800/80 hover:text-slate-200'
              }`}
            >
              <span>{catInfo.icon || '⚔️'}</span>
              <span>{catName}</span>
              <span className={`text-[10px] font-mono px-1 rounded ${active ? 'bg-amber-500/30 text-amber-200' : 'bg-slate-800 text-slate-500'}`}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Skills Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredSkills.map((skill) => {
          const catInfo = CATEGORY_MAP[skill.category] || { icon: '⚔️', en: 'sec' };
          const isClaudeEq = (equippedSkills.claude || []).includes(skill.name);
          const isGptEq = (equippedSkills.gpt || []).includes(skill.name);
          const isDeepSeekEq = (equippedSkills.deepseek || []).includes(skill.name);

          return (
            <div
              key={skill.id}
              className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-slate-700/80 hover:bg-slate-900/95 transition-all group flex flex-col justify-between shadow-md"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-lg p-1.5 rounded-lg bg-slate-800 border border-slate-700/60">
                      {skill.icon || catInfo.icon || '⚔️'}
                    </span>
                    <div>
                      <h3 className="text-sm font-bold text-slate-100 group-hover:text-amber-300 transition-colors line-clamp-1">
                        {skill.name}
                      </h3>
                      <span className="text-[10px] font-mono text-slate-500">{skill.category}</span>
                    </div>
                  </div>
                  <span
                    className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                      skill.risk === 'CRITICAL'
                        ? 'bg-rose-500/10 text-rose-300 border-rose-500/30'
                        : skill.risk === 'HIGH'
                        ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                        : 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
                    }`}
                  >
                    {skill.risk}
                  </span>
                </div>

                <p className="text-xs text-slate-400 line-clamp-2 mb-3 leading-relaxed">
                  {skill.desc}
                </p>

                {/* Equipped Badges */}
                <div className="flex flex-wrap gap-1 mb-3">
                  {isClaudeEq && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/30 flex items-center gap-1">
                      <Check className="w-2.5 h-2.5" /> Claude 装备
                    </span>
                  )}
                  {isGptEq && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                      <Check className="w-2.5 h-2.5" /> GPT-4o 装备
                    </span>
                  )}
                  {isDeepSeekEq && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/30 flex items-center gap-1">
                      <Check className="w-2.5 h-2.5" /> DeepSeek 装备
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2">
                <button
                  onClick={() => setSelectedSkill(skill)}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1 transition-colors"
                >
                  <Code className="w-3.5 h-3.5 text-slate-400" />
                  详情脚本 ({skill.script_count}个)
                </button>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleEquipSkillToAll(skill)}
                    title="一键装配至三大策略官 (Claude + GPT-4o + DeepSeek)"
                    className={`px-2 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1 border ${
                      isClaudeEq && isGptEq && isDeepSeekEq
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                        : 'bg-amber-500/10 hover:bg-amber-500/25 text-amber-300 border-amber-500/30 active:scale-95'
                    }`}
                  >
                    <Zap className="w-3 h-3 text-amber-400" />
                    {isClaudeEq && isGptEq && isDeepSeekEq ? '全员就绪' : '一键全加'}
                  </button>
                  <button
                    onClick={() => handleEquip('claude', skill)}
                    title="装备至 Claude 3.5 策略官"
                    className={`p-1.5 rounded-lg border text-xs font-mono transition-colors ${
                      isClaudeEq
                        ? 'bg-purple-900/50 border-purple-400/50 text-purple-200'
                        : 'bg-purple-950/40 hover:bg-purple-900/60 border-purple-500/30 text-purple-300'
                    }`}
                  >
                    Claude
                  </button>
                  <button
                    onClick={() => handleEquip('gpt', skill)}
                    title="装备至 GPT-4o 战术官"
                    className={`p-1.5 rounded-lg border text-xs font-mono transition-colors ${
                      isGptEq
                        ? 'bg-emerald-900/50 border-emerald-400/50 text-emerald-200'
                        : 'bg-emerald-950/40 hover:bg-emerald-900/60 border-emerald-500/30 text-emerald-300'
                    }`}
                  >
                    GPT
                  </button>
                  <button
                    onClick={() => handleEquip('deepseek', skill)}
                    title="装备至 DeepSeek-V3 推理官"
                    className={`p-1.5 rounded-lg border text-xs font-mono transition-colors ${
                      isDeepSeekEq
                        ? 'bg-blue-900/50 border-blue-400/50 text-blue-200'
                        : 'bg-blue-950/40 hover:bg-blue-900/60 border-blue-500/30 text-blue-300'
                    }`}
                  >
                    DeepSeek
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Skill Detail Modal */}
      {selectedSkill && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="w-full max-w-2xl bg-slate-900 border border-slate-700/80 rounded-2xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-3">
                <span className="text-2xl p-2 rounded-xl bg-slate-800 border border-slate-700">
                  {selectedSkill.icon || CATEGORY_MAP[selectedSkill.category]?.icon || '⚔️'}
                </span>
                <div>
                  <h2 className="text-lg font-bold text-white">{selectedSkill.name}</h2>
                  <p className="text-xs text-slate-400 font-mono">
                    分类: {selectedSkill.category} ({selectedSkill.category_en}) · 脚本数: {selectedSkill.script_count}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedSkill(null)}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white"
              >
                ×
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  技能描述与作战意图
                </h4>
                <p className="text-xs text-slate-300 bg-slate-950/60 p-3 rounded-xl border border-slate-800 leading-relaxed font-mono">
                  {selectedSkill.desc}
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    自动化执行脚本与调用载荷
                  </h4>
                  <button
                    onClick={() => copyCode(selectedSkill.content_preview || '', selectedSkill.id)}
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300 flex items-center gap-1"
                  >
                    {copiedId === selectedSkill.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    {copiedId === selectedSkill.id ? '已复制' : '复制脚本'}
                  </button>
                </div>
                <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-emerald-400 overflow-x-auto">
                  {selectedSkill.content_preview}
                </pre>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    战备装配指令
                  </h4>
                  <button
                    onClick={() => handleEquipSkillToAll(selectedSkill)}
                    className="px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-xs flex items-center gap-1.5 shadow-md shadow-amber-950/40 transition-all hover:scale-[1.02]"
                  >
                    <Flame className="w-3.5 h-3.5 text-slate-950" />
                    ⚡ 一键全员装配 (Claude + GPT + DeepSeek)
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => handleEquip('claude', selectedSkill)}
                    className="p-2.5 rounded-xl bg-purple-950/30 hover:bg-purple-900/50 border border-purple-500/30 text-purple-300 text-xs font-bold flex items-center justify-center gap-1.5"
                  >
                    <Award className="w-4 h-4 text-purple-400" />
                    Claude 3.5 Sonnet
                  </button>
                  <button
                    onClick={() => handleEquip('gpt', selectedSkill)}
                    className="p-2.5 rounded-xl bg-emerald-950/30 hover:bg-emerald-900/50 border border-emerald-500/30 text-emerald-300 text-xs font-bold flex items-center justify-center gap-1.5"
                  >
                    <Award className="w-4 h-4 text-emerald-400" />
                    GPT-4o
                  </button>
                  <button
                    onClick={() => handleEquip('deepseek', selectedSkill)}
                    className="p-2.5 rounded-xl bg-blue-950/30 hover:bg-blue-900/50 border border-blue-500/30 text-blue-300 text-xs font-bold flex items-center justify-center gap-1.5"
                  >
                    <Award className="w-4 h-4 text-blue-400" />
                    DeepSeek-V3
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
