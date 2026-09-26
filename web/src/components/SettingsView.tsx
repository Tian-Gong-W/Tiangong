import React, { useState } from 'react';
import { LoaderCircle, Plus, Settings, ShieldCheck, Trash2 } from 'lucide-react';

interface SettingsViewProps {
  settings: Record<string, any>;
  guard: Record<string, any>;
  tools: Record<string, any>;
  onAddScope: (target: string) => Promise<void>;
  onRemoveScope: (target: string) => Promise<void>;
}

const display = (value: unknown) => value === null || value === undefined || value === '' ? '—' : String(value);

export const SettingsView: React.FC<SettingsViewProps> = ({ settings, guard, tools, onAddScope, onRemoveScope }) => {
  const [target, setTarget] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const guardAllowed = Array.isArray(guard.scope?.allowed) ? guard.scope.allowed : [];
  const allowed = Array.isArray(settings.allowed_targets)
    ? settings.allowed_targets.map(String)
    : guardAllowed.map((item: any) => String(item.rule || '')).filter(Boolean);
  const defaultRules = new Set(guardAllowed.filter((item: any) => item.default).map((item: any) => String(item.rule)));
  const rules = Array.isArray(guard.rules) ? guard.rules : [];

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

  const runtimeRows: [string, unknown][] = [
    ['版本', settings.version],
    ['工作区', settings.workspace],
    ['配置文件', settings.config_path],
    ['命令超时', settings.command_timeout_seconds == null ? null : `${settings.command_timeout_seconds} 秒`],
    ['任意 Shell', settings.allow_arbitrary_shell == null ? null : settings.allow_arbitrary_shell ? '允许' : '禁止'],
  ];

  const guardRows: [string, unknown][] = [
    ['模式', guard.mode],
    ['待批准', guard.pending_approvals],
    ['工具就绪', tools.count == null ? null : `${tools.ready ?? 0}/${tools.count}`],
    ['策略规则', rules.length],
  ];

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto text-slate-100 space-y-5 max-w-6xl mx-auto">
      <div className="border-b border-slate-800 pb-4">
        <h1 className="text-xl font-bold flex items-center gap-2"><Settings className="w-4 h-4 text-cyan-400" />系统与授权范围</h1>
        <p className="text-xs text-slate-400 mt-1">读取并修改 Tiangong 的实际配置；页面不补造后端未返回的策略值。</p>
      </div>

      {error && <div className="p-3 rounded-xl border border-rose-500/30 bg-rose-950/30 text-xs text-rose-300">{error}</div>}

      <div className="grid md:grid-cols-2 gap-4">
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
          <h2 className="text-sm font-bold">运行设置</h2>
          {runtimeRows.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-3 text-xs"><span className="text-slate-500">{label}</span><span className="font-mono text-slate-300 text-right break-all">{display(value)}</span></div>
          ))}
        </div>
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
          <h2 className="text-sm font-bold flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-emerald-400" />Guard</h2>
          {guardRows.map(([label, value]) => (
            <div key={label} className="flex justify-between text-xs"><span className="text-slate-500">{label}</span><span className="font-mono text-slate-300">{display(value)}</span></div>
          ))}
        </div>
      </div>

      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div><h2 className="text-sm font-bold">授权 Scope</h2><p className="text-xs text-slate-500 mt-1">只有明确加入的目标才可进入预检和执行。</p></div>
        <form onSubmit={(event) => { event.preventDefault(); if (!target.trim()) return; act('add', async () => { await onAddScope(target.trim()); setTarget(''); }); }} className="flex gap-2">
          <input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="域名、IP 或 CIDR" className="flex-1 rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs font-mono" />
          <button disabled={!target.trim() || busy === 'add'} className="px-4 py-2 rounded-xl bg-cyan-600 disabled:opacity-40 text-xs font-bold flex items-center gap-1">{busy === 'add' ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}添加</button>
        </form>
        <div className="space-y-2">
          {allowed.length ? allowed.map((rule: string) => {
            const fixed = defaultRules.has(rule);
            return (
              <div key={rule} className="flex justify-between items-center p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-xs font-mono">{rule}</span>
                {fixed ? <span className="text-[10px] text-slate-500">后端默认</span> : <button disabled={busy === rule} onClick={() => act(rule, () => onRemoveScope(rule))} className="text-rose-300 disabled:opacity-40"><Trash2 className="w-3.5 h-3.5" /></button>}
              </div>
            );
          }) : <div className="text-xs text-slate-500">Scope 为空</div>}
        </div>
      </div>

      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <h2 className="text-sm font-bold mb-3">实际 Guard 规则</h2>
        {rules.length === 0 ? (
          <div className="text-xs text-slate-500">后端没有返回 Guard 规则记录</div>
        ) : (
          <div className="grid md:grid-cols-2 gap-2">
            {rules.map((rule: any, index: number) => (
              <div key={rule.name || index} className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <div className="flex justify-between gap-2 text-xs"><span className="font-mono">{display(rule.name)}</span><span className={rule.decision === 'allow' ? 'text-emerald-400' : rule.decision === 'approval' ? 'text-amber-400' : rule.decision ? 'text-rose-400' : 'text-slate-500'}>{display(rule.decision)}</span></div>
                <div className="text-[10px] text-slate-500 mt-1">{display(rule.detail)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
