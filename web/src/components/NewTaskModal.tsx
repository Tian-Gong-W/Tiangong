import React, { useState } from 'react';
import { LoaderCircle, Target, X } from 'lucide-react';

interface NewTaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreateTask: (target: string) => Promise<void>;
}

export const NewTaskModal: React.FC<NewTaskModalProps> = ({ isOpen, onClose, onCreateTask }) => {
  const [target, setTarget] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  if (!isOpen) return null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      await onCreateTask(target.trim());
      setTarget('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <form onSubmit={submit} className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-base font-bold text-white flex items-center gap-2"><Target className="w-5 h-5 text-cyan-400" />创建 Tiangong Mission</h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
        </div>
        <div>
          <label className="text-xs text-slate-300 font-semibold block mb-2">目标（必须已加入授权范围）</label>
          <input required value={target} onChange={(event) => setTarget(event.target.value)} placeholder="域名、IP 或 CIDR" className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm font-mono outline-none focus:border-cyan-400" />
          <p className="text-[11px] text-slate-500 mt-2">提交前会调用后端预检；范围、工具或执行节点未就绪时不会创建虚假任务。</p>
        </div>
        {error && <div className="rounded-xl border border-rose-500/30 bg-rose-950/30 px-3 py-2 text-xs text-rose-300">{error}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-xl bg-slate-800 text-xs text-slate-300">取消</button>
          <button disabled={loading || !target.trim()} className="px-5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-xs font-bold flex items-center gap-2">
            {loading && <LoaderCircle className="w-3.5 h-3.5 animate-spin" />}预检并启动
          </button>
        </div>
      </form>
    </div>
  );
};
