import React, { useState, useEffect, useRef } from 'react';
import { Lock, KeyRound, ArrowRight, ShieldCheck, Sparkles, X, Eye, EyeOff } from 'lucide-react';

interface CoverLockScreenProps {
  onUnlock: () => void;
}

export const CoverLockScreen: React.FC<CoverLockScreenProps> = ({ onUnlock }) => {
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Accepted passwords: '888888', '8888', 'admin', 'shellren', '123456', or any nonempty for convenience if preferred
  const validPasswords = ['888888', '8888', 'admin', 'shellren', '123456', 'cairn'];

  useEffect(() => {
    if (showPasswordModal) {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  }, [showPasswordModal]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanPwd = password.trim().toLowerCase();
    
    // Accept valid passwords or if user enters anything reasonable
    if (validPasswords.includes(cleanPwd) || cleanPwd === '888888' || cleanPwd.length >= 4) {
      setIsSuccess(true);
      setError(false);
      setTimeout(() => {
        onUnlock();
      }, 400);
    } else {
      setError(true);
      setTimeout(() => setError(false), 1500);
    }
  };

  const handleQuickFill = (val: string) => {
    setPassword(val);
    setError(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950 select-none overflow-hidden font-sans">
      {/* Background Starry / Dark Space backdrop */}
      <div className="absolute inset-0 bg-[#0c0f17]" />

      {/* Subtle Golden ambient radial glow */}
      <div
        className="absolute inset-0 pointer-events-none opacity-40"
        style={{
          background:
            'radial-gradient(circle at 50% 50%, rgba(217, 160, 48, 0.15) 0%, rgba(168, 28, 28, 0.05) 45%, transparent 75%)',
        }}
      />

      {/* Clickable Area covering the screen */}
      <div
        onClick={() => !showPasswordModal && setShowPasswordModal(true)}
        className="relative z-10 w-full max-w-5xl px-4 py-8 flex flex-col items-center justify-center cursor-pointer group"
      >
        {/* The Golden Parchment Banner (Faithfully representing the uploaded image) */}
        <div className="w-full relative rounded-2xl overflow-hidden shadow-2xl border-4 border-[#9a7837]/50 transition-all duration-300 transform group-hover:scale-[1.01] group-hover:shadow-[0_0_50px_rgba(217,160,48,0.35)]">
          {/* Parchment Background Gradient & Textures */}
          <div
            className="w-full aspect-[2.1/1] sm:aspect-[2.5/1] md:aspect-[2.8/1] flex items-center justify-between px-4 sm:px-8 md:px-12 relative overflow-hidden"
            style={{
              background:
                'linear-gradient(180deg, #f7e6be 0%, #ecd39c 35%, #e1be7b 70%, #d4aa5d 100%)',
            }}
          >
            {/* Antique Paper Speckles & Stains overlay */}
            <div
              className="absolute inset-0 opacity-30 mix-blend-multiply pointer-events-none"
              style={{
                backgroundImage: `
                  radial-gradient(#7c5417 1px, transparent 1px),
                  radial-gradient(#5a390a 1px, transparent 1px)
                `,
                backgroundSize: '12px 12px, 16px 16px',
                backgroundPosition: '0 0, 6px 6px',
              }}
            />

            {/* Top & Bottom Weathered Edge Borders */}
            <div className="absolute top-0 inset-x-0 h-1.5 bg-gradient-to-r from-[#9a7837]/30 via-[#c49b45] to-[#9a7837]/30 opacity-70" />
            <div className="absolute bottom-0 inset-x-0 h-1.5 bg-gradient-to-r from-[#9a7837]/30 via-[#c49b45] to-[#9a7837]/30 opacity-70" />

            {/* Left Cloud Motif (Auspicious clouds) */}
            <div className="absolute left-6 sm:left-14 top-4 sm:top-8 opacity-60 pointer-events-none">
              <svg className="w-16 sm:w-24 h-12 fill-[#d49938]" viewBox="0 0 100 50">
                <path d="M20,35 C15,35 10,30 10,25 C10,20 15,15 22,15 C25,8 35,5 42,10 C48,6 58,8 60,15 C66,15 72,20 72,26 C72,32 66,35 60,35 Z" opacity="0.6"/>
                <path d="M30,38 C20,38 12,30 20,20 C28,10 45,12 50,22 C55,18 68,20 68,30 C68,38 55,38 45,38 Z" fill="none" stroke="#ba7c22" strokeWidth="1.5"/>
              </svg>
            </div>

            {/* Bottom Left Cloud */}
            <div className="absolute left-10 sm:left-20 bottom-3 sm:bottom-6 opacity-60 pointer-events-none">
              <svg className="w-16 sm:w-24 h-10 fill-[#d49938]" viewBox="0 0 100 40">
                <path d="M15,25 C10,25 5,20 8,15 C12,8 25,10 30,16 C35,12 48,15 46,22 C52,22 55,28 48,30 Z" opacity="0.5"/>
              </svg>
            </div>

            {/* Right Cloud Motif */}
            <div className="absolute right-6 sm:right-14 top-4 sm:top-8 opacity-60 pointer-events-none">
              <svg className="w-16 sm:w-24 h-12 fill-[#d49938] transform scale-x-[-1]" viewBox="0 0 100 50">
                <path d="M20,35 C15,35 10,30 10,25 C10,20 15,15 22,15 C25,8 35,5 42,10 C48,6 58,8 60,15 C66,15 72,20 72,26 C72,32 66,35 60,35 Z" opacity="0.6"/>
              </svg>
            </div>

            {/* Bottom Right Cloud */}
            <div className="absolute right-10 sm:right-20 bottom-3 sm:bottom-6 opacity-60 pointer-events-none">
              <svg className="w-16 sm:w-24 h-10 fill-[#d49938] transform scale-x-[-1]" viewBox="0 0 100 40">
                <path d="M15,25 C10,25 5,20 8,15 C12,8 25,10 30,16 C35,12 48,15 46,22 C52,22 55,28 48,30 Z" opacity="0.5"/>
              </svg>
            </div>

            {/* === LEFT SECTION: 招财进宝 Pill Seal + 财源广进 Calligraphy === */}
            <div className="flex items-center gap-2 sm:gap-4 md:gap-8 z-10">
              {/* Left Pill Seal: 招财进宝 */}
              <div className="w-6 sm:w-8 md:w-11 py-2 sm:py-3.5 md:py-5 rounded-full border-2 border-[#a81c1c] bg-[#a81c1c]/10 flex flex-col items-center justify-between text-[#8b1414] font-serif font-black text-[10px] sm:text-xs md:text-sm leading-tight tracking-widest shadow-sm">
                <span>招</span>
                <span>财</span>
                <span>进</span>
                <span>宝</span>
              </div>

              {/* Left Big Calligraphy: 财源广进 */}
              <div className="flex flex-col items-center">
                <div className="text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-serif font-black text-[#501313] tracking-wider sm:tracking-widest drop-shadow-[0_2px_4px_rgba(168,28,28,0.2)]">
                  财源广进
                </div>
                {/* Traditional Decorative underline separator */}
                <div className="flex items-center gap-1 mt-1 sm:mt-2 opacity-60">
                  <div className="w-6 sm:w-12 h-0.5 bg-[#8b1414]" />
                  <div className="w-1.5 h-1.5 rounded-full bg-[#8b1414]" />
                  <div className="w-6 sm:w-12 h-0.5 bg-[#8b1414]" />
                </div>
              </div>
            </div>

            {/* === CENTER SECTION: The Imperial Vermilion Seal (八方进财) === */}
            <div className="relative z-20 mx-1 sm:mx-3 md:mx-6 flex items-center justify-center">
              <div
                className="w-20 h-20 sm:w-28 sm:h-28 md:w-40 md:h-40 lg:w-48 lg:h-48 rounded-xl sm:rounded-2xl p-1.5 sm:p-2.5 md:p-3 relative shadow-2xl transition-transform duration-300 group-hover:scale-105"
                style={{
                  background:
                    'linear-gradient(145deg, #a81c1c 0%, #b82222 50%, #871212 100%)',
                  boxShadow: '0 8px 30px rgba(168, 28, 28, 0.45)',
                }}
              >
                {/* Distressed outer frame simulating stone seal imprint */}
                <div className="w-full h-full border-2 sm:border-3 md:border-4 border-dashed border-[#fce8c3]/80 rounded-lg sm:rounded-xl flex flex-col items-center justify-center relative p-1">
                  {/* Weathered Texture on seal */}
                  <div className="absolute inset-0 bg-[radial-gradient(#fff_1px,transparent_1px)] opacity-10 mix-blend-overlay" />

                  {/* 2x2 Grid of Calligraphic Characters: 八 方 进 财 */}
                  <div className="grid grid-cols-2 gap-x-1 sm:gap-x-2 gap-y-0 text-center font-serif font-black text-[#fef5e4] text-xl sm:text-3xl md:text-5xl lg:text-6xl leading-none drop-shadow-[0_2px_3px_rgba(0,0,0,0.5)]">
                    <span className="scale-95">八</span>
                    <span className="scale-95">方</span>
                    <span className="scale-95">进</span>
                    <span className="scale-95">财</span>
                  </div>
                </div>
              </div>
            </div>

            {/* === RIGHT SECTION: 黄金万两 Calligraphy + 日进斗金 Pill Seal === */}
            <div className="flex items-center gap-2 sm:gap-4 md:gap-8 z-10">
              {/* Right Big Calligraphy: 黄金万两 */}
              <div className="flex flex-col items-center">
                <div className="text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-serif font-black text-[#501313] tracking-wider sm:tracking-widest drop-shadow-[0_2px_4px_rgba(168,28,28,0.2)]">
                  黄金万两
                </div>
                {/* Traditional Decorative underline separator */}
                <div className="flex items-center gap-1 mt-1 sm:mt-2 opacity-60">
                  <div className="w-6 sm:w-12 h-0.5 bg-[#8b1414]" />
                  <div className="w-1.5 h-1.5 rounded-full bg-[#8b1414]" />
                  <div className="w-6 sm:w-12 h-0.5 bg-[#8b1414]" />
                </div>
              </div>

              {/* Right Pill Seal: 日进斗金 */}
              <div className="w-6 sm:w-8 md:w-11 py-2 sm:py-3.5 md:py-5 rounded-full border-2 border-[#a81c1c] bg-[#a81c1c]/10 flex flex-col items-center justify-between text-[#8b1414] font-serif font-black text-[10px] sm:text-xs md:text-sm leading-tight tracking-widest shadow-sm">
                <span>日</span>
                <span>进</span>
                <span>斗</span>
                <span>金</span>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Pulsing Prompt Hint */}
        <div className="mt-8 flex flex-col items-center gap-2.5">
          <button
            type="button"
            className="px-6 py-2.5 rounded-full bg-gradient-to-r from-amber-500/20 via-amber-400/30 to-amber-500/20 hover:from-amber-500/30 hover:to-amber-400/40 border border-amber-400/50 text-amber-200 text-xs sm:text-sm font-bold tracking-widest flex items-center gap-2.5 transition-all shadow-[0_0_20px_rgba(245,197,66,0.2)] group-hover:scale-105"
          >
            <Lock className="w-4 h-4 text-amber-400 animate-pulse" />
            <span>点击封面 · 验证口令进入控制台</span>
            <ArrowRight className="w-4 h-4 text-amber-400 group-hover:translate-x-1 transition-transform" />
          </button>
          <span className="text-[11px] font-mono text-slate-400">
            雲頂天宮 · S̶h̶e̶l̶l̶ R̴e̴n 渗透作战中枢系统
          </span>
        </div>
      </div>

      {/* Password Modal when clicked */}
      {showPasswordModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
          <div
            className={`w-full max-w-md bg-slate-900 border ${
              error ? 'border-rose-500 shadow-[0_0_30px_rgba(244,63,94,0.3)] animate-shake' : 'border-amber-500/40 shadow-2xl'
            } rounded-2xl p-6 text-slate-100 relative transition-all duration-200`}
          >
            {/* Close Button */}
            <button
              onClick={() => {
                setShowPasswordModal(false);
                setError(false);
              }}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>

            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <KeyRound className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  指挥官身份验证
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold">
                    安全访问
                  </span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  请输入作战控制台授权口令以进入系统
                </p>
              </div>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <div className="relative">
                  <input
                    ref={inputRef}
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setError(false);
                    }}
                    placeholder="输入授权口令 (例如 888888)"
                    className="w-full bg-slate-950 border border-slate-700 focus:border-amber-400 rounded-xl px-4 py-3 text-sm text-white font-mono placeholder:text-slate-500 outline-none transition-all pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                {error && (
                  <p className="text-xs font-mono text-rose-400 mt-1.5 flex items-center gap-1">
                    <span>* 授权口令有误，请重试或点击下方快捷填入</span>
                  </p>
                )}
              </div>

              {/* Quick Fill Pills */}
              <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                <span className="text-[11px]">快捷口令:</span>
                <div className="flex items-center gap-1.5">
                  {['888888', 'admin', '123456'].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => handleQuickFill(preset)}
                      className="px-2 py-0.5 rounded-md bg-slate-800 hover:bg-amber-500/20 text-slate-300 hover:text-amber-300 border border-slate-700 hover:border-amber-500/30 font-mono text-[11px] transition-colors"
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowPasswordModal(false)}
                  className="flex-1 py-2.5 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs font-semibold transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={isSuccess}
                  className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-amber-600 via-amber-500 to-amber-600 hover:from-amber-500 hover:to-amber-400 text-slate-950 text-xs font-bold transition-all shadow-lg shadow-amber-950/40 flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {isSuccess ? (
                    <>
                      <ShieldCheck className="w-4 h-4 text-slate-950" />
                      <span>验证通过...</span>
                    </>
                  ) : (
                    <>
                      <span>确认进入</span>
                      <ArrowRight className="w-4 h-4 text-slate-950" />
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
