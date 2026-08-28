import React, { useState } from 'react';
import {
  X,
  Sliders,
  Sparkles,
  Terminal,
  Send,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { Task } from '../types';

interface InterventionModalProps {
  task: Task | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmitIntervention: (taskId: string, directive: string) => void;
}

export const InterventionModal: React.FC<InterventionModalProps> = ({
  task,
  isOpen,
  onClose,
  onSubmitIntervention,
}) => {
  const [directive, setDirective] = useState('');
  const [submitted, setSubmitted] = useState(false);

  if (!isOpen || !task) return null;

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!directive) return;
    onSubmitIntervention(task.id, directive);
    setSubmitted(true);
    setTimeout(() => {
      setSubmitted(false);
      setDirective('');
      onClose();
    }, 1200);
  };

  const quickDirectives = [
    '优先探测 /api/v2 路径下的未授权接口',
    '跳过当前高延迟端口，直接对 443 进行组件指纹比对',
    '使用自定义 Cookie Header 进行越权注入校验',
    '暂缓横向移动，先对当前突破的主机进行本地提权探索',
  ];

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sliders className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-bold text-white">指挥官指令干预</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Task Info Context */}
        <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-xs">
          <div className="text-slate-400">正在干预任务：</div>
          <div className="font-bold text-white mt-0.5">
            {task.name} ({task.code})
          </div>
          <div className="text-[11px] text-cyan-300 font-mono mt-0.5">
            当前阶段: {task.currentStage} · {task.currentAction}
          </div>
        </div>

        {/* Quick Suggestion Chips */}
        <div>
          <span className="text-[11px] font-semibold text-slate-400 block mb-2">
            快速指令预设：
          </span>
          <div className="space-y-1.5">
            {quickDirectives.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDirective(d)}
                className="w-full text-left p-2 rounded-lg bg-slate-950/60 hover:bg-slate-800 border border-slate-800 text-xs text-slate-300 hover:text-cyan-300 transition-colors"
              >
                + {d}
              </button>
            ))}
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSend} className="space-y-4 text-xs">
          <div>
            <label className="text-slate-300 font-semibold block mb-1.5">
              自定义下发自然语言指令或攻防建议：
            </label>
            <textarea
              rows={3}
              required
              placeholder="例如：对 192.168.100.15 执行弱口令爆破，字典使用 top100"
              value={directive}
              onChange={(e) => setDirective(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 resize-none"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium"
            >
              取消
            </button>

            <button
              type="submit"
              disabled={submitted}
              className="px-5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold shadow-md flex items-center gap-1.5"
            >
              {submitted ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-emerald-300" /> 指令已注入
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" /> 注入推理链
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
