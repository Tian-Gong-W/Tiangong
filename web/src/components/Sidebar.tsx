import React from 'react';
import {
  LayoutDashboard,
  Target,
  Search,
  ShieldCheck,
  Cpu,
  Server,
  Settings,
  ShieldAlert,
  Terminal,
  Activity,
  CheckCircle2,
  Sparkles,
  Lock,
} from 'lucide-react';
import { NavId } from '../types';
import { BafangJincaiAvatar } from './BrandingAssets';

interface SidebarProps {
  activeNav?: NavId;
  currentNav?: NavId;
  onSelectNav?: (nav: NavId) => void;
  setCurrentNav?: (nav: NavId) => void;
  approvalsCount?: number;
  pendingApprovalsCount?: number;
  totalFindingsCount?: number;
  runningTasksCount?: number;
  onOpenNewTaskModal?: () => void;
  onLock?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeNav,
  currentNav,
  onSelectNav,
  setCurrentNav,
  approvalsCount,
  pendingApprovalsCount,
  totalFindingsCount = 0,
  runningTasksCount = 0,
  onLock,
}) => {
  const selectedNav = activeNav || currentNav || 'dashboard';
  const handleNavChange = (nav: NavId) => {
    if (onSelectNav) onSelectNav(nav);
    if (setCurrentNav) setCurrentNav(nav);
  };
  const effectiveApprovalsCount = approvalsCount ?? pendingApprovalsCount ?? 0;

  const navItems = [
    {
      id: 'dashboard' as NavId,
      name: '仪表盘',
      enName: 'Dashboard',
      icon: LayoutDashboard,
      badge: effectiveApprovalsCount > 0 ? `${effectiveApprovalsCount} 待处理` : undefined,
      badgeColor: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
    },
    {
      id: 'tasks' as NavId,
      name: '任务',
      enName: 'Tasks',
      icon: Target,
      badge: runningTasksCount > 0 ? `${runningTasksCount} 运行` : undefined,
      badgeColor: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
    },
    {
      id: 'findings' as NavId,
      name: '发现',
      enName: 'Findings',
      icon: Search,
      badge: totalFindingsCount > 0 ? `${totalFindingsCount}` : undefined,
      badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    },
    {
      id: 'assets' as NavId,
      name: '资产',
      enName: 'Assets',
      icon: ShieldCheck,
    },
    {
      id: 'ai' as NavId,
      name: 'S̶h̶e̶l̶l̶ R̴e̴n',
      enName: 'S̶h̶e̶l̶l̶ R̴e̴n / Cairn',
      icon: Cpu,
      badge: 'Cairn',
      badgeColor: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    },
    {
      id: 'nodes' as NavId,
      name: '执行节点',
      enName: 'Nodes',
      icon: Server,
    },
  ];

  return (
    <aside className="w-64 bg-slate-900/90 backdrop-blur-md border-r border-slate-800 flex flex-col justify-between h-screen text-slate-300 select-none z-30 shrink-0">
      {/* Top Header / Branding with Image 1 Avatar */}
      <div>
        <div className="p-3.5 px-4 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Image 1 Avatar (八方进财) */}
            <BafangJincaiAvatar size="md" />

            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="font-black text-amber-300 tracking-wider text-base">
                  雲頂天宮
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 font-semibold">
                  CAIRN
                </span>
              </div>
              <p className="text-[10px] text-slate-400 font-mono truncate">
                S̶h̶e̶l̶l̶ R̴e̴n 状态空间控制台
              </p>
            </div>
          </div>
        </div>

        {/* Global Nav Menu */}
        <div className="px-3 pt-4">
          <div className="px-3 pb-2 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
            作战指挥导航
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = selectedNav === item.id;
              return (
                <button
                  key={item.id}
                  id={`nav-${item.id}`}
                  onClick={() => handleNavChange(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                    active
                      ? 'bg-cyan-500/15 text-cyan-300 font-semibold border border-cyan-500/30 shadow-sm shadow-cyan-950/50'
                      : 'hover:bg-slate-800/70 text-slate-300 hover:text-white border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      className={`w-4 h-4 transition-colors ${
                        active ? 'text-cyan-400' : 'text-slate-400'
                      }`}
                    />
                    <span className="truncate">{item.name}</span>
                  </div>

                  {item.badge && (
                    <span
                      className={`text-[11px] px-2 py-0.5 rounded-full border font-mono font-medium ${item.badgeColor}`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Footer Area: Cluster State & System Settings */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/40 space-y-2">
        {/* Node & S̶h̶e̶l̶l̶ R̴e̴n quick status capsule */}
        <div className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs">
          <div className="flex items-center justify-between text-slate-400 mb-1.5">
            <span className="flex items-center gap-1.5 text-slate-300 font-medium">
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              S̶h̶e̶l̶l̶ R̴e̴n 认知
            </span>
            <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-ping" />
              ACTIVE
            </span>
          </div>
          <p className="text-[10px] text-amber-300/90 truncate font-mono">
            雲頂天宮-Cairn-v3.5
          </p>
        </div>

        {/* Bottom Setting & Lock Buttons */}
        <div className="flex items-center gap-1.5">
          <button
            id="nav-settings"
            onClick={() => handleNavChange('settings')}
            className={`flex-1 flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-colors ${
              selectedNav === 'settings'
                ? 'bg-slate-800 text-white font-medium border border-slate-700'
                : 'text-slate-400 hover:bg-slate-800/60 hover:text-white'
            }`}
          >
            <Settings className="w-3.5 h-3.5 text-slate-400" />
            <span>系统设置</span>
          </button>

          {onLock && (
            <button
              onClick={onLock}
              title="锁定并返回封面"
              className="p-2 rounded-lg text-slate-400 hover:text-amber-300 hover:bg-slate-800/80 border border-transparent hover:border-slate-700 transition-colors"
            >
              <Lock className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
};

