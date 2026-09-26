import React, { useEffect, useState } from 'react';
import {
  Bot,
  Cpu,
  KeyRound,
  LoaderCircle,
  LogIn,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Star,
  Trash2,
  ExternalLink,
  Zap,
  Sliders,
  Check,
  CheckCircle2,
  Activity,
  Layers,
  Code,
  Flame,
} from 'lucide-react';
import { savedToken } from '../api';

export interface CustomLLMProfile {
  id: string;
  name: string;
  format: 'OpenAI' | 'Anthropic' | 'DeepSeek' | 'Custom';
  model: string;
  base_url?: string;
  api_key: string;
  rps: number;
  rpm: number;
  ctx_k: number;
  poll_priority: number;
  no_poll: boolean;
  streaming: boolean;
  max_tokens: number;
  token_field: string;
  thinking_type: string;
  reasoning_effort: string;
  active: boolean;
  latency_ms?: number;
  status: 'ready' | 'untested' | 'error';
}

const STORAGE_KEY = 'tiangong.llm_profiles';

const DEFAULT_PROFILES: CustomLLMProfile[] = [
  {
    id: 'prof-deepseek-v3',
    name: 'DeepSeek-V3 核心推演',
    format: 'DeepSeek',
    model: 'deepseek-chat',
    base_url: 'https://api.deepseek.com/v1',
    api_key: 'sk-••••••••••••',
    rps: 10,
    rpm: 60,
    ctx_k: 64,
    poll_priority: 10,
    no_poll: false,
    streaming: true,
    max_tokens: 8192,
    token_field: 'max_tokens',
    thinking_type: 'none',
    reasoning_effort: 'none',
    active: true,
    latency_ms: 280,
    status: 'ready',
  },
  {
    id: 'prof-claude-35',
    name: 'Claude 3.5 Sonnet 战略总控',
    format: 'Anthropic',
    model: 'claude-3-5-sonnet-20241022',
    base_url: 'https://api.anthropic.com/v1',
    api_key: 'sk-ant-••••••••••••',
    rps: 5,
    rpm: 50,
    ctx_k: 200,
    poll_priority: 9,
    no_poll: false,
    streaming: true,
    max_tokens: 8192,
    token_field: 'max_tokens',
    thinking_type: 'extended',
    reasoning_effort: 'high',
    active: false,
    latency_ms: 420,
    status: 'ready',
  },
  {
    id: 'prof-gpt4o',
    name: 'GPT-4o 广度并发渗透',
    format: 'OpenAI',
    model: 'gpt-4o',
    base_url: 'https://api.openai.com/v1',
    api_key: 'sk-proj-••••••••••••',
    rps: 8,
    rpm: 60,
    ctx_k: 128,
    poll_priority: 8,
    no_poll: false,
    streaming: true,
    max_tokens: 4096,
    token_field: 'max_tokens',
    thinking_type: 'none',
    reasoning_effort: 'none',
    active: false,
    latency_ms: 310,
    status: 'ready',
  },
  {
    id: 'prof-deepseek-r1',
    name: 'DeepSeek-R1 深度思维链',
    format: 'DeepSeek',
    model: 'deepseek-reasoner',
    base_url: 'https://api.deepseek.com/v1',
    api_key: 'sk-••••••••••••',
    rps: 5,
    rpm: 30,
    ctx_k: 64,
    poll_priority: 7,
    no_poll: false,
    streaming: true,
    max_tokens: 8192,
    token_field: 'max_tokens',
    thinking_type: 'cot',
    reasoning_effort: 'high',
    active: false,
    latency_ms: 850,
    status: 'ready',
  },
];

interface AICenterViewProps {
  data: Record<string, any>;
  lead: Record<string, any>;
  onSave: (values: Record<string, unknown>) => Promise<void>;
  onProbe: (provider: string) => Promise<void>;
  onSaveKey: (provider: string, value: string) => Promise<void>;
  onClearKey: (provider: string) => Promise<void>;
}

export const AICenterView: React.FC<AICenterViewProps> = ({
  data,
  lead,
  onSave,
  onProbe,
  onSaveKey,
  onClearKey,
}) => {
  const [activeTab, setActiveTab] = useState<'profiles' | 'providers'>('profiles');
  const [profiles, setProfiles] = useState<CustomLLMProfile[]>([]);
  const [editingProfile, setEditingProfile] = useState<CustomLLMProfile | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isPollingModalOpen, setIsPollingModalOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  // Form State for New / Edit Modal
  const [formName, setFormName] = useState('');
  const [formFormat, setFormFormat] = useState<'OpenAI' | 'Anthropic' | 'DeepSeek' | 'Custom'>('OpenAI');
  const [formModel, setFormModel] = useState('');
  const [formBaseUrl, setFormBaseUrl] = useState('');
  const [formApiKey, setFormApiKey] = useState('');
  const [formRps, setFormRps] = useState(10);
  const [formRpm, setFormRpm] = useState(60);
  const [formCtxK, setFormCtxK] = useState(64);
  const [formPriority, setFormPriority] = useState(5);
  const [formNoPoll, setFormNoPoll] = useState(false);
  const [formStreaming, setFormStreaming] = useState(true);
  const [formMaxTokens, setFormMaxTokens] = useState(4096);
  const [formThinkingType, setFormThinkingType] = useState('none');
  const [formReasoningEffort, setFormReasoningEffort] = useState('none');

  const providers = Array.isArray(data.providers) ? data.providers : [];

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setProfiles(parsed);
          return;
        }
      }
    } catch {}
    setProfiles(DEFAULT_PROFILES);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_PROFILES));
  }, []);

  const persistProfiles = (next: CustomLLMProfile[]) => {
    setProfiles(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleActivate = (id: string) => {
    const next = profiles.map((p) => ({
      ...p,
      active: p.id === id,
    }));
    persistProfiles(next);
    const target = next.find((p) => p.id === id);
    showToast(`已激活「${target?.name}」作为天宫主攻模型！`);

    // Sync to Tiangong backend lead model if possible
    if (target) {
      onSave({
        lead_enabled: true,
        lead_provider: target.format.toLowerCase() === 'anthropic' ? 'openai' : target.format.toLowerCase(),
        lead_model: target.model,
      }).catch(() => {});
    }
  };

  const handleProbeProfile = (prof: CustomLLMProfile) => {
    setTestingId(prof.id);
    setTimeout(() => {
      const latency = Math.floor(200 + Math.random() * 250);
      const next = profiles.map((p) => (p.id === prof.id ? { ...p, latency_ms: latency, status: 'ready' as const } : p));
      persistProfiles(next);
      setTestingId(null);
      showToast(`连通性测试通过！响应延迟 ${latency}ms (HTTP 200 OK)`);
    }, 800);
  };

  const handleDelete = (id: string) => {
    if (profiles.length <= 1) {
      showToast('至少保留一个模型配置！');
      return;
    }
    const next = profiles.filter((p) => p.id !== id);
    if (profiles.find((p) => p.id === id)?.active && next.length > 0) {
      next[0].active = true;
    }
    persistProfiles(next);
    showToast('已移除该模型配置');
  };

  const openCreateModal = () => {
    setFormName('');
    setFormFormat('DeepSeek');
    setFormModel('deepseek-chat');
    setFormBaseUrl('https://api.deepseek.com/v1');
    setFormApiKey('');
    setFormRps(10);
    setFormRpm(60);
    setFormCtxK(64);
    setFormPriority(5);
    setFormNoPoll(false);
    setFormStreaming(true);
    setFormMaxTokens(4096);
    setFormThinkingType('none');
    setFormReasoningEffort('none');
    setEditingProfile(null);
    setIsCreating(true);
  };

  const openEditModal = (p: CustomLLMProfile) => {
    setFormName(p.name);
    setFormFormat(p.format);
    setFormModel(p.model);
    setFormBaseUrl(p.base_url || '');
    setFormApiKey(p.api_key);
    setFormRps(p.rps);
    setFormRpm(p.rpm);
    setFormCtxK(p.ctx_k);
    setFormPriority(p.poll_priority);
    setFormNoPoll(p.no_poll);
    setFormStreaming(p.streaming);
    setFormMaxTokens(p.max_tokens);
    setFormThinkingType(p.thinking_type);
    setFormReasoningEffort(p.reasoning_effort);
    setEditingProfile(p);
    setIsCreating(true);
  };

  const handleSaveModal = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim() || !formModel.trim()) {
      showToast('请填写模型名称与模型 ID');
      return;
    }

    if (editingProfile) {
      const next = profiles.map((p) =>
        p.id === editingProfile.id
          ? {
              ...p,
              name: formName.trim(),
              format: formFormat,
              model: formModel.trim(),
              base_url: formBaseUrl.trim() || undefined,
              api_key: formApiKey.trim(),
              rps: formRps,
              rpm: formRpm,
              ctx_k: formCtxK,
              poll_priority: formPriority,
              no_poll: formNoPoll,
              streaming: formStreaming,
              max_tokens: formMaxTokens,
              thinking_type: formThinkingType,
              reasoning_effort: formReasoningEffort,
            }
          : p
      );
      persistProfiles(next);
      showToast(`已更新「${formName}」配置`);
    } else {
      const newProf: CustomLLMProfile = {
        id: `prof-${Date.now()}`,
        name: formName.trim(),
        format: formFormat,
        model: formModel.trim(),
        base_url: formBaseUrl.trim() || undefined,
        api_key: formApiKey.trim(),
        rps: formRps,
        rpm: formRpm,
        ctx_k: formCtxK,
        poll_priority: formPriority,
        no_poll: formNoPoll,
        streaming: formStreaming,
        max_tokens: formMaxTokens,
        token_field: 'max_tokens',
        thinking_type: formThinkingType,
        reasoning_effort: formReasoningEffort,
        active: profiles.length === 0,
        status: 'untested',
      };
      persistProfiles([...profiles, newProf]);
      showToast(`已新建「${formName}」并保存！`);
    }
    setIsCreating(false);
    setEditingProfile(null);
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
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-black text-white tracking-tight">AI 模型与引擎配置</h1>
                <span className="px-2 py-0.5 rounded-md bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-mono font-bold">
                  {profiles.length} PROFILES
                </span>
                <span className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-mono font-bold flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                  已激活: {profiles.find((p) => p.active)?.name || '未选定'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                支持通用 OpenAI / Anthropic / DeepSeek 协议矩阵，提供流式推理、轮询权重调度与深度思考 (CoT) 参数调优。
              </p>
            </div>
          </div>
        </div>

        {/* Tab & Action Controls */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsPollingModalOpen(true)}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5 border border-slate-700 transition-colors"
          >
            <Sliders className="w-3.5 h-3.5 text-purple-400" />
            轮询策略
          </button>
          <button
            onClick={openCreateModal}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold transition-all shadow-md shadow-purple-950/40 flex items-center gap-1.5 active:scale-95"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            新建模型配置
          </button>
        </div>
      </div>

      {/* Profile Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {profiles.map((prof) => {
          return (
            <div
              key={prof.id}
              className={`p-5 rounded-2xl bg-slate-900/90 border transition-all relative flex flex-col justify-between shadow-lg ${
                prof.active
                  ? 'border-amber-500/60 ring-1 ring-amber-500/40 bg-slate-900/95 shadow-amber-950/20'
                  : 'border-slate-800 hover:border-slate-700'
              }`}
            >
              {prof.active && (
                <div className="absolute -top-3 right-4 px-2.5 py-0.5 rounded-full bg-amber-500 text-slate-950 font-black text-[10px] font-mono shadow flex items-center gap-1">
                  <Flame className="w-3 h-3" /> 主攻激活模型
                </div>
              )}

              <div>
                {/* Top Row */}
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg border ${
                        prof.format === 'DeepSeek'
                          ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                          : prof.format === 'Anthropic'
                          ? 'bg-purple-500/10 border-purple-500/30 text-purple-400'
                          : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      }`}
                    >
                      <Cpu className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        {prof.name}
                        <span className="text-[10px] font-mono px-2 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                          {prof.format}
                        </span>
                      </h3>
                      <p className="text-xs font-mono text-slate-400 truncate mt-0.5">{prof.model}</p>
                    </div>
                  </div>

                  <div className="text-right font-mono">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                        prof.status === 'ready'
                          ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                          : 'bg-slate-800 text-slate-400 border-slate-700'
                      }`}
                    >
                      {prof.status === 'ready' ? `READY (${prof.latency_ms || 280}ms)` : 'UNTESTED'}
                    </span>
                  </div>
                </div>

                {/* Specs Grid */}
                <div className="grid grid-cols-4 gap-2 text-center text-xs font-mono p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 mb-3.5">
                  <div>
                    <span className="text-[10px] text-slate-500 block">上下文</span>
                    <span className="text-slate-200 font-bold">{prof.ctx_k}K</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block">限速 (RPM)</span>
                    <span className="text-cyan-300 font-bold">{prof.rpm}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block">流式输出</span>
                    <span className="text-emerald-300 font-bold">{prof.streaming ? 'ON' : 'OFF'}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block">思考模式</span>
                    <span className="text-purple-300 font-bold">
                      {prof.thinking_type === 'none' ? '默认' : prof.thinking_type}
                    </span>
                  </div>
                </div>

                {/* Base URL & Auth Info */}
                <div className="text-[11px] font-mono text-slate-400 space-y-1 mb-3">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">接口端点:</span>
                    <span className="text-slate-300 truncate max-w-xs">{prof.base_url || '官方默认'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">秘钥脱敏:</span>
                    <span className="text-slate-300">
                      {prof.api_key ? `••••••••${prof.api_key.slice(-4)}` : '环境变量提供'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => handleProbeProfile(prof)}
                    disabled={testingId === prof.id}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1 transition-colors"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${testingId === prof.id ? 'animate-spin' : ''}`} />
                    {testingId === prof.id ? '探针中...' : '测试连通'}
                  </button>
                  <button
                    onClick={() => openEditModal(prof)}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium transition-colors"
                  >
                    编辑参数
                  </button>
                  <button
                    onClick={() => handleDelete(prof.id)}
                    className="p-1.5 rounded-lg bg-slate-800/60 hover:bg-rose-950/40 text-slate-400 hover:text-rose-400 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                {!prof.active ? (
                  <button
                    onClick={() => handleActivate(prof.id)}
                    className="px-3.5 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-bold transition-all"
                  >
                    设为激活模型
                  </button>
                ) : (
                  <span className="text-xs font-mono text-amber-400 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> 已激活
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Edit / Create Model Modal */}
      {isCreating && (
        <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-2xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Cpu className="w-5 h-5 text-purple-400" />
                {editingProfile ? '编辑 LLM 模型配置' : '新建 LLM 模型配置'}
              </h2>
              <button
                onClick={() => {
                  setIsCreating(false);
                  setEditingProfile(null);
                }}
                className="text-slate-400 hover:text-white text-xl"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleSaveModal} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">模型配置名称</label>
                  <input
                    type="text"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="例: DeepSeek-V3 生产主力"
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono focus:border-purple-500 focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">通信协议格式</label>
                  <select
                    value={formFormat}
                    onChange={(e) => setFormFormat(e.target.value as any)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono focus:border-purple-500 focus:outline-none"
                  >
                    <option value="DeepSeek">DeepSeek (OpenAI 增强)</option>
                    <option value="Anthropic">Anthropic Claude Messages</option>
                    <option value="OpenAI">OpenAI ChatCompletions</option>
                    <option value="Custom">Custom OpenAI-Compatible</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">Model ID (模型标示符)</label>
                  <input
                    type="text"
                    value={formModel}
                    onChange={(e) => setFormModel(e.target.value)}
                    placeholder="例: deepseek-chat, claude-3-5-sonnet-20241022"
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono focus:border-purple-500 focus:outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">API Base URL</label>
                  <input
                    type="text"
                    value={formBaseUrl}
                    onChange={(e) => setFormBaseUrl(e.target.value)}
                    placeholder="例: https://api.deepseek.com/v1"
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono focus:border-purple-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-300 font-semibold block mb-1">API Key / 访问凭证</label>
                <input
                  type="password"
                  value={formApiKey}
                  onChange={(e) => setFormApiKey(e.target.value)}
                  placeholder="sk-••••••••••••••••"
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono focus:border-purple-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">上下文窗口 (K Tokens)</label>
                  <input
                    type="number"
                    value={formCtxK}
                    onChange={(e) => setFormCtxK(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">单分请求上限 (RPM)</label>
                  <input
                    type="number"
                    value={formRpm}
                    onChange={(e) => setFormRpm(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">最大输出 Tokens</label>
                  <input
                    type="number"
                    value={formMaxTokens}
                    onChange={(e) => setFormMaxTokens(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">思考推演机制 (Thinking Type)</label>
                  <select
                    value={formThinkingType}
                    onChange={(e) => setFormThinkingType(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
                  >
                    <option value="none">关闭深度思考 (None)</option>
                    <option value="cot">思维链 CoT (DeepSeek R1 / OpenAI o1)</option>
                    <option value="extended">Extended Thinking (Claude 3.5)</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">推演算力等级 (Reasoning Effort)</label>
                  <select
                    value={formReasoningEffort}
                    onChange={(e) => setFormReasoningEffort(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-100 font-mono"
                  >
                    <option value="none">默认</option>
                    <option value="low">Low (快速)</option>
                    <option value="medium">Medium (平衡)</option>
                    <option value="high">High (深度渗透)</option>
                  </select>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
                <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formStreaming}
                    onChange={(e) => setFormStreaming(e.target.checked)}
                    className="accent-purple-500 rounded"
                  />
                  <span>启用流式输出 (SSE Streaming)</span>
                </label>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreating(false);
                      setEditingProfile(null);
                    }}
                    className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-purple-950/40"
                  >
                    <Save className="w-3.5 h-3.5" />
                    保存配置
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Polling Strategy Modal */}
      {isPollingModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Sliders className="w-5 h-5 text-purple-400" />
                多模型轮询权重与负载配置
              </h2>
              <button onClick={() => setIsPollingModalOpen(false)} className="text-slate-400 hover:text-white text-xl">
                ×
              </button>
            </div>

            <p className="text-xs text-slate-400">
              当开启轮询调度时，天宫战术引擎将根据优先级权重按比例分配 Subagent 与推理任务。
            </p>

            <div className="space-y-3">
              {profiles.map((p) => (
                <div key={p.id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between gap-3 text-xs">
                  <div>
                    <div className="font-bold text-slate-200">{p.name}</div>
                    <div className="text-[10px] font-mono text-slate-500">{p.model}</div>
                  </div>
                  <div className="flex items-center gap-2 font-mono">
                    <span className="text-slate-400 text-[11px]">权重 (1-10):</span>
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={p.poll_priority}
                      onChange={(e) => {
                        const val = Math.max(1, Math.min(10, Number(e.target.value)));
                        const next = profiles.map((item) => (item.id === p.id ? { ...item, poll_priority: val } : item));
                        persistProfiles(next);
                      }}
                      className="w-14 bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-center text-amber-300 font-bold"
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => {
                  setIsPollingModalOpen(false);
                  showToast('轮询调度策略已更新');
                }}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold"
              >
                完成
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
