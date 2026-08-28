import React, { useState } from 'react';
import { KeyRound, LoaderCircle, Lock, ShieldCheck } from 'lucide-react';

interface CoverLockScreenProps {
  onUnlock: (token: string) => Promise<void>;
}

export const CoverLockScreen: React.FC<CoverLockScreenProps> = ({ onUnlock }) => {
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!token.trim()) return;
    setLoading(true);
    setError('');
    try {
      await onUnlock(token);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '验证失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950 text-slate-100 flex items-center justify-center p-5">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(245,158,11,0.12),transparent_55%)]" />
      <form onSubmit={submit} className="relative w-full max-w-md rounded-3xl border border-amber-500/30 bg-slate-900/95 p-7 shadow-2xl space-y-5">
        <div className="w-12 h-12 rounded-2xl border border-amber-500/30 bg-amber-500/10 flex items-center justify-center text-amber-300">
          <Lock className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">雲頂天宮 Mission Control</h1>
          <p className="text-xs text-slate-400 mt-1">此口令由服务端验证；页面不再接受演示口令。</p>
        </div>
        <label className="block space-y-2">
          <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5"><KeyRound className="w-3.5 h-3.5" />控制台访问口令</span>
          <input
            type="password"
            autoFocus
            autoComplete="current-password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none focus:border-amber-400"
            placeholder="TONMEN_WEB_TOKEN"
          />
        </label>
        {error && <div className="rounded-xl border border-rose-500/30 bg-rose-950/30 px-3 py-2 text-xs text-rose-300">{error}</div>}
        <button disabled={loading || !token.trim()} className="w-full rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-40 py-3 text-sm font-black text-slate-950 flex items-center justify-center gap-2">
          {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
          验证并读取真实数据
        </button>
      </form>
    </div>
  );
};
