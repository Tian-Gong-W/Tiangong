import React, { useEffect, useState } from 'react';
import { Bot, KeyRound, LoaderCircle, RefreshCw, Save, ShieldCheck, Trash2 } from 'lucide-react';

interface AICenterViewProps {
  data: Record<string, any>;
  lead: Record<string, any>;
  onSave: (values: Record<string, unknown>) => Promise<void>;
  onProbe: (provider: string) => Promise<void>;
  onSaveKey: (provider: string, value: string) => Promise<void>;
  onClearKey: (provider: string) => Promise<void>;
}

export const AICenterView: React.FC<AICenterViewProps> = ({ data, lead, onSave, onProbe, onSaveKey, onClearKey }) => {
  const settings = data.local_settings || {};
  const providers = Array.isArray(data.providers) ? data.providers : [];
  const [enabled, setEnabled] = useState(Boolean(lead.enabled));
  const [model, setModel] = useState(String(settings.lead_model || lead.model || 'gpt-5.6'));
  const [pool, setPool] = useState<string[]>(Array.isArray(settings.pool) ? settings.pool : []);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    setEnabled(Boolean(lead.enabled));
    setModel(String(data.local_settings?.lead_model || lead.model || 'gpt-5.6'));
    setPool(Array.isArray(data.local_settings?.pool) ? data.local_settings.pool : []);
  }, [data, lead]);

  const act = async (id: string, action: () => Promise<void>) => {
    setBusy(id);
    setError('');
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } finally { setBusy(''); }
  };

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto text-slate-100 space-y-5 max-w-6xl mx-auto">
      <div className="border-b border-slate-800 pb-4"><h1 className="text-xl font-bold flex items-center gap-2"><Bot className="w-4 h-4 text-purple-400" />AI Provider Hub</h1><p className="text-xs text-slate-400 mt-1">显示 Tiangong ProviderHub 的实际配置、连接和历史用量</p></div>
      {error && <div className="rounded-xl border border-rose-500/30 bg-rose-950/30 p-3 text-xs text-rose-300">{error}</div>}
      <div className="p-5 rounded-2xl bg-slate-900/85 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between"><div><div className="text-sm font-bold">Lead AI</div><div className="text-xs text-slate-500 mt-1">执行、批准、范围及计划变更权限均为 false</div></div><label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} className="accent-purple-500" />启用 OpenAI Lead</label></div>
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="text-xs text-slate-400">模型<input value={model} onChange={(event) => setModel(event.target.value)} className="mt-1.5 w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2.5 text-slate-100 font-mono" /></label>
          <div className="text-xs text-slate-400">当前状态<div className="mt-1.5 rounded-xl bg-slate-950 border border-slate-800 px-3 py-2.5 font-mono text-slate-200">{lead.provider || 'disabled'} · {lead.key_configured ? 'Key 已配置' : 'Key 未配置'}</div></div>
        </div>
        <button onClick={() => act('settings', () => onSave({ lead_enabled: enabled, lead_model: model, pool }))} className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-bold flex items-center gap-1.5"><Save className="w-3.5 h-3.5" />保存到后端</button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {providers.map((provider: any) => {
          const apiKey = provider.auth_mode === 'api_key';
          const configured = Boolean(provider.key_configured || provider.local_secret?.configured);
          return (
            <div key={provider.id} className="p-5 rounded-2xl bg-slate-900/85 border border-slate-800 space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div><div className="text-sm font-bold text-white">{provider.label}</div><div className="text-[11px] text-slate-500 font-mono mt-1">{provider.transport} · {provider.default_model || 'CLI'}</div></div>
                <span className={`text-[10px] font-bold ${configured || provider.last_probe?.ready ? 'text-emerald-400' : 'text-amber-400'}`}>{provider.last_probe?.ready ? 'READY' : configured ? 'CONFIGURED' : 'NOT CONFIGURED'}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
                <div className="p-2 rounded-lg bg-slate-950"><span className="block text-slate-500">调用</span>{provider.usage?.calls || 0}</div>
                <div className="p-2 rounded-lg bg-slate-950"><span className="block text-slate-500">Tokens</span>{provider.usage?.total_tokens || 0}</div>
                <div className="p-2 rounded-lg bg-slate-950"><span className="block text-slate-500">失败</span>{provider.usage?.failures || 0}</div>
              </div>
              <label className="text-xs flex items-center gap-2"><input type="checkbox" checked={pool.includes(provider.id)} onChange={(event) => setPool((current) => event.target.checked ? [...current.filter((id) => id !== provider.id), provider.id] : current.filter((id) => id !== provider.id))} className="accent-purple-500" />加入 Council Provider 池</label>
              {apiKey ? (
                <div className="space-y-2">
                  <div className="relative"><KeyRound className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" /><input type="password" value={keys[provider.id] || ''} onChange={(event) => setKeys({ ...keys, [provider.id]: event.target.value })} placeholder={configured ? '已配置；输入新值可替换' : '输入 API Key'} className="w-full pl-9 pr-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs" /></div>
                  <div className="flex gap-2"><button disabled={!keys[provider.id] || busy === provider.id} onClick={() => act(provider.id, async () => { await onSaveKey(provider.id, keys[provider.id]); setKeys({ ...keys, [provider.id]: '' }); })} className="flex-1 py-2 rounded-lg bg-cyan-600 disabled:opacity-40 text-xs font-bold">{busy === provider.id ? '处理中…' : '安全保存 Key'}</button>{configured && <button onClick={() => act(provider.id, () => onClearKey(provider.id))} className="p-2 rounded-lg bg-rose-500/10 text-rose-300"><Trash2 className="w-4 h-4" /></button>}</div>
                </div>
              ) : <div className="text-xs text-slate-500">{provider.setup_hint || (provider.installed ? 'CLI 已安装' : 'CLI 未安装')}</div>}
              <button onClick={() => act(`probe:${provider.id}`, () => onProbe(provider.id))} className="w-full py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs flex items-center justify-center gap-1.5">{busy === `probe:${provider.id}` ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}检查连接</button>
            </div>
          );
        })}
      </div>
      {providers.length === 0 && <div className="p-10 text-center rounded-2xl border border-dashed border-slate-700 text-sm text-slate-500">后端没有 Provider 记录</div>}
      <div className="text-[11px] text-slate-500 flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5" />浏览器不读取已保存的密钥值，API 返回仅包含配置状态。</div>
    </div>
  );
};
