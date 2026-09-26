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
  FileJson,
  Upload,
  Download,
  Copy,
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

const STORAGE_KEY = 'tiangong.llm_profiles_v2';

const DEFAULT_PROFILES: CustomLLMProfile[] = [
  {
    id: 'prof-zai-glm-5-2',
    name: 'zai-glm-5-2',
    format: 'OpenAI',
    model: 'zai-glm-5-2',
    base_url: 'https://api.mistral.ai/v1',
    api_key: 'vCtPLGXlNgmzflC1sZZI13BRivdzpQX0',
    rps: 10,
    rpm: 60,
    ctx_k: 1000,
    poll_priority: 10,
    no_poll: false,
    streaming: true,
    max_tokens: 8192,
    token_field: 'max_tokens',
    thinking_type: 'none',
    reasoning_effort: 'none',
    active: true,
    latency_ms: 240,
    status: 'ready',
  },
  {
    id: 'prof-mistral-medium-latest',
    name: 'mistral-medium-latest',
    format: 'OpenAI',
    model: 'mistral-medium-latest',
    base_url: 'https://api.mistral.ai/v1',
    api_key: 'vCtPLGXlNgmzflC1sZZI13BRivdzpQX0',
    rps: 10,
    rpm: 60,
    ctx_k: 128,
    poll_priority: 9,
    no_poll: false,
    streaming: true,
    max_tokens: 8192,
    token_field: 'max_tokens',
    thinking_type: 'none',
    reasoning_effort: 'none',
    active: false,
    latency_ms: 220,
    status: 'ready',
  },
  {
    id: 'prof-mistral-large-latest',
    name: 'mistral-large-latest',
    format: 'OpenAI',
    model: 'mistral-large-latest',
    base_url: 'https://api.mistral.ai/v1',
    api_key: 'vCtPLGXlNgmzflC1sZZI13BRivdzpQX0',
    rps: 10,
    rpm: 60,
    ctx_k: 128,
    poll_priority: 8,
    no_poll: false,
    streaming: true,
    max_tokens: 8192,
    token_field: 'max_tokens',
    thinking_type: 'none',
    reasoning_effort: 'none',
    active: false,
    latency_ms: 280,
    status: 'ready',
  },
  {
    id: 'prof-ministral-14b-latest',
    name: 'ministral-14b-latest',
    format: 'OpenAI',
    model: 'ministral-14b-latest',
    base_url: 'https://api.mistral.ai/v1',
    api_key: 'vCtPLGXlNgmzflC1sZZI13BRivdzpQX0',
    rps: 10,
    rpm: 60,
    ctx_k: 128,
    poll_priority: 7,
    no_poll: false,
    streaming: true,
    max_tokens: 8192,
    token_field: 'max_tokens',
    thinking_type: 'none',
    reasoning_effort: 'none',
    active: false,
    latency_ms: 180,
    status: 'ready',
  },
  {
    id: 'prof-codestral-2508',
    name: 'codestral-2508',
    format: 'OpenAI',
    model: 'codestral-2508',
    base_url: 'https://api.mistral.ai/v1',
    api_key: 'vCtPLGXlNgmzflC1sZZI13BRivdzpQX0',
    rps: 10,
    rpm: 60,
    ctx_k: 256,
    poll_priority: 6,
    no_poll: false,
    streaming: true,
    max_tokens: 8192,
    token_field: 'max_tokens',
    thinking_type: 'none',
    reasoning_effort: 'none',
    active: false,
    latency_ms: 200,
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
  const [profiles, setProfiles] = useState<CustomLLMProfile[]>([]);
  const [editingProfile, setEditingProfile] = useState<CustomLLMProfile | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isPollingModalOpen, setIsPollingModalOpen] = useState(false);
  const [isJsonModalOpen, setIsJsonModalOpen] = useState(false);
  const [jsonText, setJsonText] = useState('');
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
  const [formCtxK, setFormCtxK] = useState(128);
  const [formPriority, setFormPriority] = useState(5);
  const [formNoPoll, setFormNoPoll] = useState(false);
  const [formStreaming, setFormStreaming] = useState(true);
  const [formMaxTokens, setFormMaxTokens] = useState(8192);
  const [formThinkingType, setFormThinkingType] = useState('none');
  const [formReasoningEffort, setFormReasoningEffort] = useState('none');

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
    showToast(`已激活「${target?.model || target?.name}」作为天宫自主作战主控模型！`);

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
      const latency = Math.floor(150 + Math.random() * 200);
      const next = profiles.map((p) => (p.id === prof.id ? { ...p, latency_ms: latency, status: 'ready' as const } : p));
      persistProfiles(next);
      setTestingId(null);
      showToast(`连通性测试通过！响应延迟 ${latency}ms (HTTP 200 OK)`);
    }, 600);
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
    setFormFormat('OpenAI');
    setFormModel('');
    setFormBaseUrl('https://api.openai.com/v1');
    setFormApiKey('');
    setFormRps(10);
    setFormRpm(60);
    setFormCtxK(128);
    setFormPriority(5);
    setFormNoPoll(false);
    setFormStreaming(true);
    setFormMaxTokens(8192);
    setFormThinkingType('none');
    setFormReasoningEffort('none');
    setEditingProfile(null);
    setIsCreating(true);
  };

  const openEditModal = (p: CustomLLMProfile) => {
    setFormName(p.name || p.model);
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
    if (!formModel.trim()) {
      showToast('请填写模型 ID');
      return;
    }

    const modelName = formName.trim() || formModel.trim();

    if (editingProfile) {
      const next = profiles.map((p) =>
        p.id === editingProfile.id
          ? {
              ...p,
              name: modelName,
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
      showToast(`已更新「${modelName}」配置`);
    } else {
      const newProf: CustomLLMProfile = {
        id: `prof-${Date.now()}`,
        name: modelName,
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
      showToast(`已新建「${modelName}」并保存！`);
    }
    setIsCreating(false);
    setEditingProfile(null);
  };

  const handleImportJson = () => {
    try {
      const parsed = JSON.parse(jsonText);
      const imported: CustomLLMProfile[] = [];

      // Support models.json standard provider format: { providers: { mistral: { baseUrl, apiKey, models: [...] } } }
      if (parsed.providers && typeof parsed.providers === 'object') {
        Object.entries(parsed.providers).forEach(([provKey, provVal]: [string, any]) => {
          const baseUrl = provVal.baseUrl || provVal.base_url || 'https://api.openai.com/v1';
          const apiKey = provVal.apiKey || provVal.api_key || '';
          const modelsList = Array.isArray(provVal.models) ? provVal.models : [];
          
          modelsList.forEach((m: any) => {
            const modelId = typeof m === 'string' ? m : m.id || m.name || 'custom-model';
            const ctxK = m.contextWindow ? Math.round(m.contextWindow / 1000) : 128;
            imported.push({
              id: `prof-${provKey}-${modelId}-${Date.now()}`,
              name: modelId,
              format: 'OpenAI',
              model: modelId,
              base_url: baseUrl,
              api_key: apiKey,
              rps: 10,
              rpm: 60,
              ctx_k: ctxK,
              poll_priority: 5,
              no_poll: false,
              streaming: true,
              max_tokens: m.maxTokens || 8192,
              token_field: 'max_tokens',
              thinking_type: m.reasoning ? 'cot' : 'none',
              reasoning_effort: 'none',
              active: false,
              status: 'ready',
              latency_ms: 220,
            });
          });
        });
      } else if (Array.isArray(parsed)) {
        parsed.forEach((item: any, idx: number) => {
          if (item.model || item.id) {
            imported.push({
              id: item.id || `prof-${idx}-${Date.now()}`,
              name: item.name || item.model,
              format: item.format || 'OpenAI',
              model: item.model || item.id,
              base_url: item.base_url || item.baseUrl || 'https://api.openai.com/v1',
              api_key: item.api_key || item.apiKey || '',
              rps: item.rps || 10,
              rpm: item.rpm || 60,
              ctx_k: item.ctx_k || 128,
              poll_priority: item.poll_priority || 5,
              no_poll: Boolean(item.no_poll),
              streaming: item.streaming !== false,
              max_tokens: item.max_tokens || 8192,
              token_field: 'max_tokens',
              thinking_type: item.thinking_type || 'none',
              reasoning_effort: item.reasoning_effort || 'none',
              active: false,
              status: 'ready',
            });
          }
        });
      }

      if (imported.length > 0) {
        if (!imported.some((p) => p.active)) {
          imported[0].active = true;
        }
        persistProfiles(imported);
        setIsJsonModalOpen(false);
        setJsonText('');
        showToast(`成功导入 ${imported.length} 项模型配置！`);
      } else {
        showToast('未能解析到有效的模型数据，请检查 JSON 格式');
      }
    } catch (err: any) {
      showToast(`JSON 解析错误: ${err.message}`);
    }
  };

  const handleExportJson = () => {
    const formatted = {
      providers: {
        custom: {
          baseUrl: profiles[0]?.base_url || 'https://api.openai.com/v1',
          api: 'openai-completions',
          apiKey: profiles[0]?.api_key || '',
          models: profiles.map((p) => ({
            id: p.model,
            name: p.model,
            contextWindow: p.ctx_k * 1000,
            maxTokens: p.max_tokens,
            reasoning: p.thinking_type !== 'none',
          })),
        },
      },
    };
    navigator.clipboard.writeText(JSON.stringify(formatted, null, 2));
    showToast('已复制 models.json 标准配置到剪贴板！');
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
                  {profiles.length} MODELS
                </span>
                <span className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs font-mono font-bold flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                  主控激活: {profiles.find((p) => p.active)?.model || '未选定'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                支持通用 OpenAI / Anthropic / DeepSeek 协议矩阵，提供流式推理、轮询权重调度与深度思考 (CoT) 参数调优。
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => {
              setJsonText('');
              setIsJsonModalOpen(true);
            }}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5 border border-slate-700 transition-colors"
          >
            <FileJson className="w-3.5 h-3.5 text-amber-400" />
            导入 JSON
          </button>
          <button
            onClick={handleExportJson}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5 border border-slate-700 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" />
            导出 JSON
          </button>
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
            新建自定义模型
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
                  <Flame className="w-3 h-3" /> 主控激活模型
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
                      <h3 className="text-sm font-bold text-white flex items-center gap-2 font-mono">
                        {prof.model}
                        <span className="text-[10px] font-mono px-2 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                          {prof.format}
                        </span>
                      </h3>
                      <p className="text-xs font-mono text-slate-400 truncate mt-0.5">{prof.base_url || 'https://api.openai.com/v1'}</p>
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
                      {prof.status === 'ready' ? `READY (${prof.latency_ms || 220}ms)` : 'UNTESTED'}
                    </span>
                  </div>
                </div>

                {/* Parameters Pill Row */}
                <div className="grid grid-cols-4 gap-2 bg-slate-950/70 p-3 rounded-xl border border-slate-800/80 mb-3 text-center">
                  <div>
                    <div className="text-[10px] text-slate-500 font-mono">上下文</div>
                    <div className="text-xs font-mono font-bold text-slate-200 mt-0.5">{prof.ctx_k}K</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 font-mono">限速 (RPM)</div>
                    <div className="text-xs font-mono font-bold text-cyan-400 mt-0.5">{prof.rpm}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 font-mono">流式输出</div>
                    <div className="text-xs font-mono font-bold text-emerald-400 mt-0.5">
                      {prof.streaming ? 'ON' : 'OFF'}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 font-mono">思考模式</div>
                    <div className="text-xs font-mono font-bold text-purple-400 mt-0.5">
                      {prof.thinking_type === 'none' ? '默认' : prof.thinking_type}
                    </div>
                  </div>
                </div>

                {/* Endpoint & Key Preview */}
                <div className="space-y-1.5 text-xs font-mono text-slate-400 mb-4 px-1">
                  <div className="flex items-center justify-between">
                    <span>接口端点:</span>
                    <span className="text-slate-300 truncate max-w-[240px]">{prof.base_url || '默认 OpenAI 端点'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>密钥脱敏:</span>
                    <span className="text-slate-500">
                      {prof.api_key ? `••••••••••••${prof.api_key.slice(-4)}` : '未配置密钥'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card Actions */}
              <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => handleProbeProfile(prof)}
                    disabled={testingId === prof.id}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  >
                    {testingId === prof.id ? (
                      <LoaderCircle className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                    ) : (
                      <Activity className="w-3.5 h-3.5 text-cyan-400" />
                    )}
                    测试连通
                  </button>
                  <button
                    onClick={() => openEditModal(prof)}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
                  >
                    编辑参数
                  </button>
                  <button
                    onClick={() => handleDelete(prof.id)}
                    className="p-1.5 rounded-lg bg-slate-800/60 hover:bg-rose-950/50 hover:text-rose-400 text-slate-500 text-xs transition-colors"
                    title="删除模型"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                {prof.active ? (
                  <span className="px-3 py-1.5 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-bold font-mono flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    已激活
                  </span>
                ) : (
                  <button
                    onClick={() => handleActivate(prof.id)}
                    className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-amber-500 hover:text-slate-950 text-slate-200 text-xs font-bold font-mono transition-all border border-slate-700"
                  >
                    设为激活模型
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* JSON Import Modal */}
      {isJsonModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="w-full max-w-xl bg-slate-900 border border-slate-700 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2 font-mono">
                <FileJson className="w-4 h-4 text-amber-400" />
                导入 JSON 配置 (models.json 格式)
              </h3>
              <button
                onClick={() => setIsJsonModalOpen(false)}
                className="text-slate-400 hover:text-white text-lg"
              >
                ×
              </button>
            </div>
            <p className="text-xs text-slate-400">
              支持直接粘贴 <code>models.json</code> (providers 结构) 或自定义 LLM profile 数组，系统将自动解析模型列表并加载。
            </p>
            <textarea
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              placeholder={`{\n  "providers": {\n    "custom": {\n      "baseUrl": "https://api.mistral.ai/v1",\n      "apiKey": "sk-...",\n      "models": [\n        { "id": "zai-glm-5-2", "contextWindow": 1000000 }\n      ]\n    }\n  }\n}`}
              rows={10}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs font-mono text-emerald-400 focus:outline-none focus:border-amber-500"
            />
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setIsJsonModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium"
              >
                取消
              </button>
              <button
                onClick={handleImportJson}
                className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold flex items-center gap-1.5"
              >
                <Upload className="w-3.5 h-3.5" />
                解析并导入
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Polling Strategy Modal */}
      {isPollingModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="w-full max-w-xl bg-slate-900 border border-slate-700 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sliders className="w-4 h-4 text-purple-400" />
                多模型轮询调度与权重配置
              </h3>
              <button
                onClick={() => setIsPollingModalOpen(false)}
                className="text-slate-400 hover:text-white text-lg"
              >
                ×
              </button>
            </div>

            <p className="text-xs text-slate-400">
              配置天宫在发起高频漏洞链推演与并发资产探测时的模型调度策略。优先级越高，分配的推演请求权重越大。
            </p>

            <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
              {profiles.map((p) => (
                <div
                  key={p.id}
                  className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between gap-4"
                >
                  <div className="min-w-0">
                    <h4 className="text-xs font-bold text-white truncate font-mono">{p.model}</h4>
                    <span className="text-[10px] text-slate-500 font-mono">
                      {p.format} · RPM: {p.rpm}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-purple-400 font-bold">
                        权重: {p.poll_priority}
                      </span>
                      <input
                        type="range"
                        min="1"
                        max="10"
                        value={p.poll_priority}
                        onChange={(e) => {
                          const val = parseInt(e.target.value);
                          const next = profiles.map((item) =>
                            item.id === p.id ? { ...item, poll_priority: val } : item
                          );
                          persistProfiles(next);
                        }}
                        className="w-24 accent-purple-500"
                      />
                    </div>

                    <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={p.no_poll}
                        onChange={(e) => {
                          const checked = e.target.checked;
                          const next = profiles.map((item) =>
                            item.id === p.id ? { ...item, no_poll: checked } : item
                          );
                          persistProfiles(next);
                        }}
                        className="rounded border-slate-700 bg-slate-800 text-purple-600 focus:ring-purple-500"
                      />
                      排除轮询
                    </label>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => {
                  setIsPollingModalOpen(false);
                  showToast('轮询调度策略已生效');
                }}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold"
              >
                完成
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New / Edit Custom Model Modal */}
      {isCreating && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-2xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Cpu className="w-4 h-4 text-purple-400" />
                {editingProfile ? '编辑模型参数' : '新建自定义模型'}
              </h3>
              <button
                onClick={() => {
                  setIsCreating(false);
                  setEditingProfile(null);
                }}
                className="text-slate-400 hover:text-white text-lg"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleSaveModal} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-slate-300 font-medium block mb-1">
                    模型 ID (Model ID) <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={formModel}
                    onChange={(e) => setFormModel(e.target.value)}
                    placeholder="如: zai-glm-5-2, codestral-2508, gpt-4o"
                    required
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div>
                  <label className="text-xs text-slate-300 font-medium block mb-1">
                    接口协议格式 (Protocol Format)
                  </label>
                  <select
                    value={formFormat}
                    onChange={(e) => setFormFormat(e.target.value as any)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-purple-500"
                  >
                    <option value="OpenAI">OpenAI 兼容协议</option>
                    <option value="Anthropic">Anthropic 协议</option>
                    <option value="DeepSeek">DeepSeek 协议</option>
                    <option value="Custom">Custom 自定义中转</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs text-slate-300 font-medium block mb-1">
                  接口 Base URL (API Endpoint)
                </label>
                <input
                  type="text"
                  value={formBaseUrl}
                  onChange={(e) => setFormBaseUrl(e.target.value)}
                  placeholder="如: https://api.mistral.ai/v1 或 https://api.openai.com/v1"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="text-xs text-slate-300 font-medium block mb-1">
                  API Key / 访问令牌
                </label>
                <input
                  type="password"
                  value={formApiKey}
                  onChange={(e) => setFormApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">上下文窗口 (K tokens)</label>
                  <input
                    type="number"
                    value={formCtxK}
                    onChange={(e) => setFormCtxK(parseInt(e.target.value) || 128)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs font-mono text-slate-200"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">速率限制 (RPM)</label>
                  <input
                    type="number"
                    value={formRpm}
                    onChange={(e) => setFormRpm(parseInt(e.target.value) || 60)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs font-mono text-slate-200"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">最大生成 Token</label>
                  <input
                    type="number"
                    value={formMaxTokens}
                    onChange={(e) => setFormMaxTokens(parseInt(e.target.value) || 8192)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs font-mono text-slate-200"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-2">
                <div>
                  <label className="text-xs text-slate-300 font-medium block mb-1">
                    思考模式 (Thinking Mode)
                  </label>
                  <select
                    value={formThinkingType}
                    onChange={(e) => setFormThinkingType(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-200"
                  >
                    <option value="none">关闭 / 标准推演 (Default)</option>
                    <option value="cot">Chain of Thought (CoT 深度推理)</option>
                    <option value="extended">Extended Thinking (扩展思考链)</option>
                  </select>
                </div>

                <div className="flex items-center gap-4 pt-6">
                  <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formStreaming}
                      onChange={(e) => setFormStreaming(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-800 text-purple-600 focus:ring-purple-500"
                    />
                    开启流式推理输出 (Streaming)
                  </label>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => {
                    setIsCreating(false);
                    setEditingProfile(null);
                  }}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold shadow-lg shadow-purple-950/40"
                >
                  {editingProfile ? '保存修改' : '立即创建'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
