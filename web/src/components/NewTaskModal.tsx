import React, { useState } from 'react';
import {
  X,
  Target,
} from 'lucide-react';
import { Task } from '../types';

interface NewTaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreateTask: (newTask: Partial<Task>) => void;
}

export const NewTaskModal: React.FC<NewTaskModalProps> = ({
  isOpen,
  onClose,
  onCreateTask,
}) => {
  const [name, setName] = useState('');
  const [target, setTarget] = useState('');
  const [scopeNotes, setScopeNotes] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !target) return;

    onCreateTask({
      name,
      target,
      type: 'RedTeam',
      code: `#Task-${Math.floor(100000 + Math.random() * 900000)}`,
      status: 'running',
      currentStage: '侦察阶段',
      currentAction: '初始化端点探测与资产指纹识别',
      runtimeMinutes: 1,
      completedSteps: 1,
      totalSteps: 20,
      progress: 5,
      findingsCount: { critical: 0, high: 0, medium: 0, low: 0 },
      assetsCount: 1,
      assignedNode: 'Worker-Edge-01 (北京)',
      executionEvents: [
        {
          id: `evt-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          timeDisplay: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          tool: 'nmap-scanner',
          target: target,
          phase: 'recon',
          title: '网络服务探测',
          status: 'completed',
          duration: '3s',
          outputSummary: `完成针对 ${target} 的存活与端口侦察`,
          rawOutput: `[+] Host is up. Initiating SYN Stealth Scan against ${target}`,
          workerNode: 'Worker-Edge-01',
        },
      ],
      chainNodes: [
        {
          id: 'n1',
          label: target,
          type: 'target',
          status: 'active',
          subLabel: '初始作战目标',
        },
      ],
      chainEdges: [],
      assetTree: {
        id: `dom-${Date.now()}`,
        domain: target,
        scopeStatus: 'in_scope',
        totalHosts: 1,
        checkedHosts: 1,
        hosts: [
          {
            ip: target.includes('.') ? target : '127.0.0.1',
            status: 'checked',
            services: [
              {
                port: 443,
                protocol: 'tcp',
                service: 'https',
                status: 'checked',
                findingIds: [],
              },
            ],
          },
        ],
      },
    });

    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-bold text-white">发起新渗透任务</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="text-slate-300 font-semibold block mb-1.5">
              任务名称
            </label>
            <input
              type="text"
              required
              placeholder="例如：HW行动 - 集团核心网关安全性评估"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            />
          </div>

          <div>
            <label className="text-slate-300 font-semibold block mb-1.5">
              测试目标 (域名 / IP / CIDR)
            </label>
            <input
              type="text"
              required
              placeholder="例如：target.example.com 或 192.168.1.0/24"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-slate-100 font-mono placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            />
          </div>

          <div>
            <label className="text-slate-300 font-semibold block mb-1.5">
              授权范围与补充约束 (可选)
            </label>
            <textarea
              rows={2}
              placeholder="例如：禁止利用 3306 端口，禁止对生产数据库进行写操作"
              value={scopeNotes}
              onChange={(e) => setScopeNotes(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 resize-none"
            />
          </div>

          <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium"
            >
              取消
            </button>

            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold shadow-lg shadow-cyan-950/50"
            >
              启动 AI 渗透推演
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
