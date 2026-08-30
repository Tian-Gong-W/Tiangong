import React, { useEffect, useState } from 'react';
import { Bot, ExternalLink, KeyRound, LoaderCircle, LogIn, RefreshCw, Save, ShieldCheck, Trash2 } from 'lucide-react';
import { savedToken } from '../api';

interface AICenterViewProps {
  data: Record<string, any>;
  lead: Record<string, any>;
  onSave: (values: Record<string, unknown>) => Promise<void>;
  onProbe: (provider: string) => Promise<void>;
  onSaveKey: (provider: string, value: string) => Promise<void>;
  onClearKey: (provider: string) => Promise<void>;
}

async function startProviderLogin(provider: string): Promise<Record<string, any>> {
  const response = await fetch(`/api/ai/providers/${encodeURIComponent(provider)}/login`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${savedToken()}`,
      'Content-Type': 'application/json',
    },
    body: '{}',
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(String(payload?.error || payload?.technical || `HTTP ${response.status}`));
  return payload;
}

export const AICenterView: React.FC<AICenterViewProps> = ({ data, lead, onSave, onProbe, onSaveKey, onClearKey }) => {
  const settings = data.local_settings || {};
  const authority = data.authority || {};
  const providers = Array.isArray(data.providers) ? data.providers : [];
  const leadOptions = Array.isArray(data.lead_provider_options) ? data.lead_provider_options : [];
  const [enabled, setEnabled] = useState(Boolean(lead.enabled));
  const [leadProvider, setLeadProvider] = useState(String(settings.lead_provider || lead.provider || 'disabled'));
  const [model, setModel] = useState(String(settings.lead_model || lead.model || ''));
  const [pool, setPool] = useState<string[]>(Array.isArray(settings.pool) ? settings.pool : []);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [loginSessions, setLoginSessions] = useState<Record<string, Record<string, any>>>({});
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    setEnabled(Boolean(lead.enabled));
    setLeadProvider(String(data.local_settings?.lead_provider || lead.provider || 'disabled'));
    setModel(String(data.local_settings?.lead_model || lead.model || ''));
    setPool(Array.isArray(data.local_settings?.pool) ? data.local_settings.pool : []);
  }, [data, lead]);

  const act = async (id: string, action: () => Promise<void>) => {
    setBusy(id);
    setError('');
    try {
      await action();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy('');
    }
  };

  const saveLeadSettings = () => act('settings', async () => {
    const values: Record<string, unknown> = {
      lead_enabled: enabled,
      lead_provider: enabled ? leadProvider : 'disabled',
      pool,
    };
    if (model.trim()) values.lead_model = model.trim();
    await onSave(values);
  });

  const selectLeadProvider = (providerId: string) => {
    setLeadProvider(providerId);
    setEnabled(providerId !== 'disabled');
    const option = leadOptions.find((item: any) => item.id === providerId);
    if (option?.default_model) setModel(String(option.default_model));
  };

  const login = (provider: any) => act(`login:${provider.id}`, async () => {
    // Open a placeholder synchronously so Safari/Chrome treat the eventual navigation
    // as the same user gesture instead of blocking it as an async popup.
    const popup = window.open('about:blank', '_blank');
    const session = await startProviderLogin(provider.id);
    setLoginSessions((current) => ({ ...current, [provider.id]: session }));
    if (session.auth_url && popup) {
      popup.opener = null;
      popup.location.href = String(session.auth_url);
    } else if (popup) {
      popup.close();
    }
  });

  const authorityText = [
    `执行 ${authority.execution ? '允许' : '无'}`,
    `批准 ${authority.approval ? '允许' : '无'}`,
    `范围 ${authority.scope ? '允许' : '无'}`,
    `计划变更 ${authority.plan_mutation ? '允许' : '无'}`,
  ].join(' · ');

  return (
    <div className="flex-1 p-4 sm:p-6 md:p-8 overflow-y-auto text-slate-100 space-y-5 max-w-6xl w-full mx-auto">
      <div className="border-b border-slate-800 pb-4">
        <h1 className="text-xl font-bold flex items-center gap-2"><Bot className="w-4 h-4 text-purple-400" />AI Provider Hub</h1>
        <p className="text-xs text-slate-400 mt-1">显示 Tiangong ProviderHub 返回的实际配置、认证、连接和历史用量</p>
      </div>

      {error && <div className="rounded-xl border border-rose-500/30 bg-rose-950/30 p-3 text-xs text-rose-300 break-words">{error}</div>}

      <div className="p-4 sm:p-5 rounded-2xl bg-slate-900/85 border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold">Lead AI</div>
            <div className="text-xs text-slate-500 mt-1">{authorityText}</div>
          </div>
          <label className="flex items-center gap-2 text-xs shrink-0">
            <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} className="accent-purple-500" />启用 Lead AI
          </label>
        </div>

        <div className="grid sm:grid-cols-3 gap-3">
          <label className="text-xs text-slate-400">
            Provider
            <select
              value={enabled ? leadProvider : 'disabled'}
              onChange={(event) => selectLeadProvider(event.target.value)}
              className="mt-1.5 w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2.5 text-slate-100 font-mono"
            >
              {(leadOptions.length ? leadOptions : [{ id: 'disabled', label: 'Disabled' }, { id: 'openai', label: 'OpenAI API' }, { id: 'deepseek', label: 'DeepSeek API' }, { id: 'mistral', label: 'Mistral API' }]).map((option: any) => (
                <option key={option.id} value={option.id}>{option.label || option.id}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-400">
            模型 / Agent
            <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="未配置" className="mt-1.5 w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2.5 text-slate-100 font-mono" />
          </label>
          <div className="text-xs text-slate-400">
            当前状态
            <div className="mt-1.5 min-h-[42px] rounded-xl bg-slate-950 border border-slate-800 px-3 py-2.5 font-mono text-slate-200 break-words">
              {String(lead.provider || (enabled ? leadProvider || 'provider 未配置' : 'disabled'))} · {lead.key_configured ? 'Key 已配置' : 'Key 未配置'} · {model || '模型未配置'}
            </div>
          </div>
        </div>

        {lead.error && <div className="rounded-xl border border-amber-500/20 bg-amber-950/20 px-3 py-2 text-[11px] text-amber-300 break-words">{String(lead.error)}</div>}

        <button disabled={busy === 'settings'} onClick={saveLeadSettings} className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-xs font-bold flex items-center gap-1.5">
          {busy === 'settings' ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}保存到后端
        </button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {providers.map((provider: any) => {
          const apiKey = provider.auth_mode === 'api_key';
          const configured = Boolean(provider.key_configured || provider.local_secret?.configured);
          const authenticated = apiKey ? configured : Boolean(provider.authenticated || provider.last_probe?.authenticated);
          const ready = Boolean(provider.runtime_ready || provider.last_probe?.runtime_ready || provider.last_probe?.ready);
          const installed = provider.installed !== false;
          const session = loginSessions[provider.id] || provider.auth_session;
          const statusText = ready ? 'READY' : authenticated ? 'AUTHENTICATED' : configured ? 'CONFIGURED' : installed ? 'NOT CONFIGURED' : 'UNAVAILABLE';
          const statusClass = ready ? 'text-emerald-400' : authenticated ? 'text-cyan-300' : configured ? 'text-cyan-300' : 'text-amber-400';
          return (
            <div key={provider.id} className="p-4 sm:p-5 rounded-2xl bg-slate-900/85 border border-slate-800 space-y-4 min-w-0">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-bold text-white truncate">{provider.label || provider.id}</div>
                  <div className="text-[11px] text-slate-500 font-mono mt-1 break-words">{provider.transport || '—'} · {provider.default_model || '—'}</div>
                </div>
                <span className={`text-[10px] font-bold shrink-0 ${statusClass}`}>{statusText}</span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
                <div className="p-2 rounded-lg bg-slate-950"><span className="block text-slate-500">调用</span>{provider.usage?.calls ?? 0}</div>
                <div className="p-2 rounded-lg bg-slate-950"><span className="block text-slate-500">Tokens</span>{provider.usage?.total_tokens ?? 0}</div>
                <div className="p-2 rounded-lg bg-slate-950"><span className="block text-slate-500">失败</span>{provider.usage?.failures ?? 0}</div>
              </div>

              {(provider.last_probe?.detail || provider.runtime_blocker) && (
                <div className="text-[11px] text-slate-500 rounded-lg bg-slate-950 px-3 py-2 break-words">
                  {String(provider.last_probe?.detail || provider.runtime_blocker)}
                </div>
              )}

              <label className="text-xs flex items-center gap-2">
                <input type="checkbox" checked={pool.includes(provider.id)} onChange={(event) => setPool((current) => event.target.checked ? [...current.filter((id) => id !== provider.id), provider.id] : current.filter((id) => id !== provider.id))} className="accent-purple-500" />加入 Council Provider 池
              </label>

              {apiKey ? (
                <div className="space-y-2">
                  <div className="relative">
                    <KeyRound className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input type="password" value={keys[provider.id] || ''} onChange={(event) => setKeys({ ...keys, [provider.id]: event.target.value })} placeholder={configured ? '已配置；输入新值可替换' : '输入 API Key'} className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs" />
                  </div>
                  <div className="flex gap-2">
                    <button disabled={!keys[provider.id] || busy === provider.id} onClick={() => act(provider.id, async () => { await onSaveKey(provider.id, keys[provider.id]); setKeys((current) => ({ ...current, [provider.id]: '' })); })} className="flex-1 py-2 rounded-lg bg-cyan-600 disabled:opacity-40 text-xs font-bold">{busy === provider.id ? '处理中…' : '保存 Key'}</button>
                    {configured && <button disabled={busy === provider.id} onClick={() => act(provider.id, () => onClearKey(provider.id))} className="p-2 rounded-lg bg-rose-500/10 text-rose-300 disabled:opacity-40"><Trash2 className="w-4 h-4" /></button>}
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="text-xs text-slate-500 break-words">{provider.setup_hint || (installed ? 'CLI 已安装；登录后由官方 CLI 保管会话。' : 'CLI 未安装')}</div>
                  <button
                    disabled={!installed || busy === `login:${provider.id}` || authenticated}
                    onClick={() => login(provider)}
                    className="w-full py-2 rounded-lg bg-purple-600/80 hover:bg-purple-500 disabled:opacity-40 text-xs font-bold flex items-center justify-center gap-1.5"
                  >
                    {busy === `login:${provider.id}` ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <LogIn className="w-3.5 h-3.5" />}
                    {authenticated ? '已登录' : '一键网页登录'}
                  </button>
                  {session && (session.auth_url || session.user_code || session.detail) && (
                    <div className="rounded-xl border border-purple-500/20 bg-purple-950/20 p-3 space-y-2 text-[11px]">
                      {session.user_code && <div><span className="text-slate-500">一次性代码：</span><span className="font-mono font-bold text-purple-200 select-all">{String(session.user_code)}</span></div>}
                      {session.auth_url && (
                        <a href={String(session.auth_url)} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-cyan-300 break-all">
                          <ExternalLink className="w-3.5 h-3.5 shrink-0" />打开官方授权页面
                        </a>
                      )}
                      {session.detail && <div className="text-slate-400 break-words">{String(session.detail)}</div>}
                    </div>
                  )}
                </div>
              )}

              <button onClick={() => act(`probe:${provider.id}`, () => onProbe(provider.id))} className="w-full py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs flex items-center justify-center gap-1.5">
                {busy === `probe:${provider.id}` ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}检查连接
              </button>
            </div>
          );
        })}
      </div>

      {providers.length === 0 && <div className="p-10 text-center rounded-2xl border border-dashed border-slate-700 text-sm text-slate-500">后端没有 Provider 记录</div>}
      <div className="text-[11px] text-slate-500 flex items-start gap-1.5"><ShieldCheck className="w-3.5 h-3.5 mt-0.5 shrink-0" /><span>浏览器不读取已保存的 API Key 或 CLI 凭据值；网页登录只显示官方授权 URL / 一次性代码，READY 必须由真实连接探测确认。</span></div>
    </div>
  );
};
