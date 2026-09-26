import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, Eye, EyeOff, KeyRound, LoaderCircle, Lock, ShieldCheck, X } from 'lucide-react';

interface CoverLockScreenProps {
  onUnlock: (token: string) => Promise<void>;
}

export const CoverLockScreen: React.FC<CoverLockScreenProps> = ({ onUnlock }) => {
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!showPasswordModal) return;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 100);
    return () => window.clearTimeout(timer);
  }, [showPasswordModal]);

  const handleSubmit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const token = password.trim();
    if (!token || loading) return;
    setLoading(true);
    setError('');
    try {
      await onUnlock(token);
      setIsSuccess(true);
    } catch (reason) {
      setIsSuccess(false);
      setError(reason instanceof Error ? reason.message : '服务端验证失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950 select-none overflow-hidden font-sans">
      <div className="absolute inset-0 bg-[#0c0f17]" />
      <div
        className="absolute inset-0 pointer-events-none opacity-50"
        style={{
          background:
            'radial-gradient(circle at 50% 48%, rgba(217,160,48,0.16) 0%, rgba(168,28,28,0.06) 43%, transparent 74%)',
        }}
      />
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-amber-400/40 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-amber-400/20 to-transparent" />

      <div
        onClick={() => !showPasswordModal && setShowPasswordModal(true)}
        className="relative z-10 w-full max-w-5xl px-4 py-8 flex flex-col items-center justify-center cursor-pointer group"
      >
        <div className="w-full relative rounded-2xl overflow-hidden shadow-2xl border-4 border-[#9a7837]/50 transition-all duration-300 transform group-hover:scale-[1.01] group-hover:shadow-[0_0_50px_rgba(217,160,48,0.35)]">
          <div
            className="w-full aspect-[2.1/1] sm:aspect-[2.5/1] md:aspect-[2.8/1] flex items-center justify-between px-4 sm:px-8 md:px-12 relative overflow-hidden"
            style={{
              background:
                'linear-gradient(180deg, #f7e6be 0%, #ecd39c 35%, #e1be7b 70%, #d4aa5d 100%)',
            }}
          >
            <div
              className="absolute inset-0 opacity-30 mix-blend-multiply pointer-events-none"
              style={{
                backgroundImage:
                  'radial-gradient(#7c5417 1px, transparent 1px), radial-gradient(#5a390a 1px, transparent 1px)',
                backgroundSize: '12px 12px, 16px 16px',
                backgroundPosition: '0 0, 6px 6px',
              }}
            />
            <div className="absolute top-0 inset-x-0 h-1.5 bg-gradient-to-r from-[#9a7837]/30 via-[#c49b45] to-[#9a7837]/30 opacity-70" />
            <div className="absolute bottom-0 inset-x-0 h-1.5 bg-gradient-to-r from-[#9a7837]/30 via-[#c49b45] to-[#9a7837]/30 opacity-70" />

            <div className="absolute left-6 sm:left-14 top-4 sm:top-8 opacity-60 pointer-events-none">
              <svg className="w-16 sm:w-24 h-12 fill-[#d49938]" viewBox="0 0 100 50" aria-hidden="true">
                <path d="M20,35 C15,35 10,30 10,25 C10,20 15,15 22,15 C25,8 35,5 42,10 C48,6 58,8 60,15 C66,15 72,20 72,26 C72,32 66,35 60,35 Z" opacity="0.6" />
                <path d="M30,38 C20,38 12,30 20,20 C28,10 45,12 50,22 C55,18 68,20 68,30 C68,38 55,38 45,38 Z" fill="none" stroke="#ba7c22" strokeWidth="1.5" />
              </svg>
            </div>
            <div className="absolute left-10 sm:left-20 bottom-3 sm:bottom-6 opacity-60 pointer-events-none">
              <svg className="w-16 sm:w-24 h-10 fill-[#d49938]" viewBox="0 0 100 40" aria-hidden="true">
                <path d="M15,25 C10,25 5,20 8,15 C12,8 25,10 30,16 C35,12 48,15 46,22 C52,22 55,28 48,30 Z" opacity="0.5" />
              </svg>
            </div>
            <div className="absolute right-6 sm:right-14 top-4 sm:top-8 opacity-60 pointer-events-none">
              <svg className="w-16 sm:w-24 h-12 fill-[#d49938] transform scale-x-[-1]" viewBox="0 0 100 50" aria-hidden="true">
                <path d="M20,35 C15,35 10,30 10,25 C10,20 15,15 22,15 C25,8 35,5 42,10 C48,6 58,8 60,15 C66,15 72,20 72,26 C72,32 66,35 60,35 Z" opacity="0.6" />
              </svg>
            </div>
            <div className="absolute right-10 sm:right-20 bottom-3 sm:bottom-6 opacity-60 pointer-events-none">
              <svg className="w-16 sm:w-24 h-10 fill-[#d49938] transform scale-x-[-1]" viewBox="0 0 100 40" aria-hidden="true">
                <path d="M15,25 C10,25 5,20 8,15 C12,8 25,10 30,16 C35,12 48,15 46,22 C52,22 55,28 48,30 Z" opacity="0.5" />
              </svg>
            </div>

            <div className="flex items-center gap-2 sm:gap-4 md:gap-8 z-10">
              <div className="w-6 sm:w-8 md:w-11 py-2 sm:py-3.5 md:py-5 rounded-full border-2 border-[#a81c1c] bg-[#a81c1c]/10 flex flex-col items-center justify-between text-[#8b1414] font-serif font-black text-[10px] sm:text-xs md:text-sm leading-tight tracking-widest shadow-sm">
                <span>招</span><span>财</span><span>进</span><span>宝</span>
              </div>
              <div className="flex flex-col items-center">
                <div className="text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-serif font-black text-[#501313] tracking-wider sm:tracking-widest drop-shadow-[0_2px_4px_rgba(168,28,28,0.2)]">财源广进</div>
                <div className="flex items-center gap-1 mt-1 sm:mt-2 opacity-60">
                  <div className="w-6 sm:w-12 h-0.5 bg-[#8b1414]" /><div className="w-1.5 h-1.5 rounded-full bg-[#8b1414]" /><div className="w-6 sm:w-12 h-0.5 bg-[#8b1414]" />
                </div>
              </div>
            </div>

            <div className="relative z-20 mx-1 sm:mx-3 md:mx-6 flex items-center justify-center">
              <div
                className="w-20 h-20 sm:w-28 sm:h-28 md:w-40 md:h-40 lg:w-48 lg:h-48 rounded-xl sm:rounded-2xl p-1.5 sm:p-2.5 md:p-3 relative shadow-2xl transition-transform duration-300 group-hover:scale-105"
                style={{ background: 'linear-gradient(145deg, #a81c1c 0%, #b82222 50%, #871212 100%)', boxShadow: '0 8px 30px rgba(168,28,28,0.45)' }}
              >
                <div className="w-full h-full border-2 sm:border-3 md:border-4 border-dashed border-[#fce8c3]/80 rounded-lg sm:rounded-xl flex flex-col items-center justify-center relative p-1">
                  <div className="absolute inset-0 bg-[radial-gradient(#fff_1px,transparent_1px)] opacity-10 mix-blend-overlay" />
                  <div className="grid grid-cols-2 gap-x-1 sm:gap-x-2 gap-y-0 text-center font-serif font-black text-[#fef5e4] text-xl sm:text-3xl md:text-5xl lg:text-6xl leading-none drop-shadow-[0_2px_3px_rgba(0,0,0,0.5)]">
                    <span>八</span><span>方</span><span>进</span><span>财</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-4 md:gap-8 z-10">
              <div className="flex flex-col items-center">
                <div className="text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-serif font-black text-[#501313] tracking-wider sm:tracking-widest drop-shadow-[0_2px_4px_rgba(168,28,28,0.2)]">黄金万两</div>
                <div className="flex items-center gap-1 mt-1 sm:mt-2 opacity-60">
                  <div className="w-6 sm:w-12 h-0.5 bg-[#8b1414]" /><div className="w-1.5 h-1.5 rounded-full bg-[#8b1414]" /><div className="w-6 sm:w-12 h-0.5 bg-[#8b1414]" />
                </div>
              </div>
              <div className="w-6 sm:w-8 md:w-11 py-2 sm:py-3.5 md:py-5 rounded-full border-2 border-[#a81c1c] bg-[#a81c1c]/10 flex flex-col items-center justify-between text-[#8b1414] font-serif font-black text-[10px] sm:text-xs md:text-sm leading-tight tracking-widest shadow-sm">
                <span>日</span><span>进</span><span>斗</span><span>金</span>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-col items-center gap-2.5">
          <button
            type="button"
            className="px-6 py-2.5 rounded-full bg-gradient-to-r from-amber-500/20 via-amber-400/30 to-amber-500/20 hover:from-amber-500/30 hover:to-amber-400/40 border border-amber-400/50 text-amber-200 text-xs sm:text-sm font-bold tracking-widest flex items-center gap-2.5 transition-all shadow-[0_0_20px_rgba(245,197,66,0.2)] group-hover:scale-105"
          >
            <Lock className="w-4 h-4 text-amber-400 animate-pulse" />
            <span>点击封面 · 验证口令进入控制台</span>
            <ArrowRight className="w-4 h-4 text-amber-400 group-hover:translate-x-1 transition-transform" />
          </button>
          <span className="text-[11px] font-mono text-slate-400">雲頂天宮 · Mission Control · Tiangong</span>
        </div>
      </div>

      {showPasswordModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
          <form
            onSubmit={handleSubmit}
            className={`w-full max-w-md bg-slate-900 border ${error ? 'border-rose-500 shadow-[0_0_30px_rgba(244,63,94,0.3)]' : isSuccess ? 'border-emerald-500/60 shadow-[0_0_30px_rgba(16,185,129,0.18)]' : 'border-amber-500/40 shadow-2xl'} rounded-2xl p-6 text-slate-100 relative transition-all duration-200`}
          >
            <button
              type="button"
              disabled={loading}
              onClick={() => { setShowPasswordModal(false); setError(''); setPassword(''); setIsSuccess(false); }}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-40"
              aria-label="关闭"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400"><KeyRound className="w-5 h-5" /></div>
              <div>
                <h3 className="text-base font-bold">进入雲頂天宮</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">口令直接提交给 Tiangong 服务端验证</p>
              </div>
            </div>

            <label className="block text-xs text-slate-300 font-semibold mb-2">控制台访问口令</label>
            <div className="relative">
              <input
                ref={inputRef}
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(event) => { setPassword(event.target.value); setError(''); setIsSuccess(false); }}
                placeholder="TONMEN_WEB_TOKEN"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 pl-4 pr-11 py-3 text-sm outline-none focus:border-amber-400 font-mono"
              />
              <button type="button" onClick={() => setShowPassword((value) => !value)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-200" aria-label={showPassword ? '隐藏口令' : '显示口令'}>
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            {error && <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-950/30 px-3 py-2 text-xs text-rose-300">{error}</div>}
            {isSuccess && <div className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-950/30 px-3 py-2 text-xs text-emerald-300">服务端验证通过</div>}

            <button
              disabled={loading || !password.trim()}
              className="mt-5 w-full rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 hover:from-amber-400 hover:to-yellow-300 disabled:opacity-40 py-3 text-sm font-black text-slate-950 flex items-center justify-center gap-2"
            >
              {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
              {loading ? '正在验证…' : '验证并进入控制台'}
            </button>
            <p className="mt-3 text-center text-[10px] text-slate-600">浏览器仅在本次标签页会话保存已验证口令。</p>
          </form>
        </div>
      )}
    </div>
  );
};
