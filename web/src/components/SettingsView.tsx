import React, { useState } from 'react';
import {
  Settings,
  ShieldCheck,
  Key,
  Lock,
  Database,
  FileCheck,
  Save,
  Check,
} from 'lucide-react';

export const SettingsView: React.FC = () => {
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-slate-950 text-slate-100 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Settings className="w-4 h-4 text-cyan-400" />
            <h1 className="text-xl font-bold text-white tracking-wide">
              系统与权限配置 (Settings)
            </h1>
          </div>
          <p className="text-xs text-slate-400">
            企业授权策略、默认拦截级别、审计日志存储与作战凭据管理
          </p>
        </div>

        <button
          onClick={handleSave}
          className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition-all shadow-md flex items-center gap-2 self-start sm:self-auto cursor-pointer"
        >
          {saved ? <Check className="w-4 h-4 text-emerald-300" /> : <Save className="w-4 h-4" />}
          {saved ? '配置已保存' : '保存系统策略'}
        </button>
      </div>

      {/* Global Mission Grant Policy */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-cyan-400" />
          <h2 className="text-sm font-bold text-white">默认授权策略 (Mission Grant Policy)</h2>
        </div>

        <p className="text-xs text-slate-400">
          控制全平台在执行高危破坏性操作（如写入数据库、提权执行、跨网段横向移动）时的默认审批拦截策略。
        </p>

        <div className="space-y-3 pt-2">
          <label className="flex items-center justify-between p-3.5 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer">
            <div>
              <div className="text-xs font-bold text-slate-200">
                开启跨网段横向移动前置拦截 (Lateral Movement Approval)
              </div>
              <div className="text-[11px] text-slate-400">
                当 AI 尝试从 DMZ 跳板跨越至内部生产核心网段时，必须经指挥官确认
              </div>
            </div>
            <input
              type="checkbox"
              defaultChecked
              className="w-4 h-4 accent-cyan-500"
            />
          </label>

          <label className="flex items-center justify-between p-3.5 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer">
            <div>
              <div className="text-xs font-bold text-slate-200">
                禁止破坏性 Payload (Safe Exploit Only)
              </div>
              <div className="text-[11px] text-slate-400">
                仅允许无害化回显 PoC 探测，严禁执行 Drop Table、Format、DoS 等危险指令
              </div>
            </div>
            <input
              type="checkbox"
              defaultChecked
              className="w-4 h-4 accent-cyan-500"
            />
          </label>
        </div>
      </div>

      {/* Audit Trails */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-3 shadow-xl">
        <div className="flex items-center gap-2">
          <FileCheck className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-bold text-white">合规与不可篡改审计</h2>
        </div>

        <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 text-xs font-mono text-slate-300 space-y-2">
          <div className="flex justify-between">
            <span className="text-slate-500">审计日志加密存储：</span>
            <span className="text-emerald-400 font-bold">AES-256 GCM (启用)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">证据哈希签名：</span>
            <span className="text-cyan-300 font-bold">SHA-256 (全量校验通过)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">审计日志留存天数：</span>
            <span className="text-slate-300">180 天</span>
          </div>
        </div>
      </div>
    </div>
  );
};
