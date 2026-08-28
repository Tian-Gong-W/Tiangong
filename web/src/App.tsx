/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, LoaderCircle, RefreshCw } from 'lucide-react';
import { ControlPlaneSnapshot, NavItemId } from './types';
import {
  addScope,
  approveMission,
  authenticate,
  forgetToken,
  loadControlPlane,
  mapWorkers,
  preflightMission,
  probeProvider,
  probeWorker,
  removeScope,
  resumeMission,
  saveProviderKey,
  clearProviderKey,
  savedToken,
  startMission,
  updateAIConfig,
} from './api';
import { Sidebar } from './components/Sidebar';
import { DashboardView } from './components/DashboardView';
import { TasksListView } from './components/TasksListView';
import { FindingsGlobalView } from './components/FindingsGlobalView';
import { AssetsGlobalView } from './components/AssetsGlobalView';
import { AICenterView } from './components/AICenterView';
import { NodesGlobalView } from './components/NodesGlobalView';
import { SettingsView } from './components/SettingsView';
import { TaskWarRoom } from './components/TaskWarRoom';
import { NewTaskModal } from './components/NewTaskModal';
import { LaicaiBackground } from './components/BrandingAssets';
import { CoverLockScreen } from './components/CoverLockScreen';

const emptySnapshot: ControlPlaneSnapshot = {
  status: {},
  tasks: [],
  findings: [],
  tools: { count: 0, ready: 0, tools: [] },
  guard: {},
  settings: {},
  providers: { providers: [] },
  workers: { workers: [], execution_mode: 'local' },
};

export default function App() {
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [activeNav, setActiveNav] = useState<NavItemId>('dashboard');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<ControlPlaneSnapshot>(emptySnapshot);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [isNewTaskOpen, setIsNewTaskOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimer = useRef<number | null>(null);

  const showToast = useCallback((message: string) => {
    setToastMessage(message);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToastMessage(null), 3500);
  }, []);

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const next = await loadControlPlane();
      setSnapshot(next);
      setLoadError('');
    } catch (error) {
      const status = (error as Error & { status?: number }).status;
      if (status === 401) {
        forgetToken();
        setIsUnlocked(false);
      }
      setLoadError(error instanceof Error ? error.message : String(error));
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  const unlock = async (token: string) => {
    await authenticate(token);
    setIsUnlocked(true);
  };

  useEffect(() => {
    if (!savedToken()) return;
    authenticate(savedToken())
      .then(() => setIsUnlocked(true))
      .catch(() => forgetToken());
  }, []);

  useEffect(() => {
    if (!isUnlocked) return;
    refresh();
    const timer = window.setInterval(() => refresh(true), 5000);
    return () => window.clearInterval(timer);
  }, [isUnlocked, refresh]);

  const selectedTask = useMemo(
    () => snapshot.tasks.find((task) => task.id === selectedTaskId) || null,
    [snapshot.tasks, selectedTaskId],
  );

  const handleApprove = async (runId: string) => {
    try {
      const result = await approveMission(runId);
      showToast(String(result.message || '批准已受理'));
      await refresh(true);
    } catch (error) {
      showToast(error instanceof Error ? error.message : String(error));
    }
  };

  const handleCreateTask = async (target: string) => {
    const preflight = await preflightMission(target);
    if (!preflight.ready_to_start) {
      const blockers = Array.isArray(preflight.blockers)
        ? preflight.blockers.map((item: any) => item.detail || item.message || item.code).filter(Boolean)
        : [];
      throw new Error(blockers.join('；') || '预检未通过，请检查授权范围和工具状态。');
    }
    const created = await startMission(target);
    setIsNewTaskOpen(false);
    setSelectedTaskId(String(created.id));
    showToast('任务已由 Tiangong 后端受理');
    await refresh(true);
  };

  if (!isUnlocked) return <CoverLockScreen onUnlock={unlock} />;

  const pendingApprovals = snapshot.tasks.filter((task) => task.status === 'waiting_approval').length;
  const runningTasks = snapshot.tasks.filter((task) => task.status === 'running').length;

  return (
    <div className="flex h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans relative">
      <LaicaiBackground />
      <Sidebar
        activeNav={activeNav}
        onSelectNav={(id) => {
          setActiveNav(id);
          setSelectedTaskId(null);
        }}
        approvalsCount={pendingApprovals}
        totalFindingsCount={snapshot.findings.length}
        runningTasksCount={runningTasks}
        onLock={() => {
          forgetToken();
          setIsUnlocked(false);
        }}
      />

      <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
        {loadError && (
          <div className="mx-5 mt-4 rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-xs text-rose-200 flex items-center justify-between gap-3 z-20">
            <span className="flex items-center gap-2"><AlertTriangle className="w-4 h-4" />{loadError}</span>
            <button onClick={() => refresh()} className="flex items-center gap-1 text-white"><RefreshCw className="w-3.5 h-3.5" />重试</button>
          </div>
        )}
        {loading && snapshot.tasks.length === 0 ? (
          <div className="flex-1 flex items-center justify-center text-sm text-slate-400 gap-2">
            <LoaderCircle className="w-4 h-4 animate-spin" />正在读取 Tiangong 控制面数据…
          </div>
        ) : selectedTask ? (
          <TaskWarRoom
            task={selectedTask}
            allFindings={snapshot.findings}
            onBack={() => setSelectedTaskId(null)}
            onApprove={handleApprove}
          />
        ) : (
          <>
            {activeNav === 'dashboard' && (
              <DashboardView
                tasks={snapshot.tasks}
                findings={snapshot.findings}
                status={snapshot.status}
                tools={snapshot.tools}
                onSelectTask={(task) => setSelectedTaskId(task.id)}
                onApprove={handleApprove}
                onOpenNewTaskModal={() => setIsNewTaskOpen(true)}
                onNavigateFindings={() => setActiveNav('findings')}
                onRefresh={() => refresh()}
              />
            )}
            {activeNav === 'tasks' && (
              <TasksListView
                tasks={snapshot.tasks}
                onSelectTask={(task) => setSelectedTaskId(task.id)}
                onOpenNewTaskModal={() => setIsNewTaskOpen(true)}
                onResume={async (id) => {
                  try {
                    await resumeMission(id);
                    showToast('后端已受理恢复请求');
                    await refresh(true);
                  } catch (error) {
                    showToast(error instanceof Error ? error.message : String(error));
                  }
                }}
              />
            )}
            {activeNav === 'findings' && (
              <FindingsGlobalView
                findings={snapshot.findings}
                onSelectFindingTask={(id) => setSelectedTaskId(id)}
              />
            )}
            {activeNav === 'assets' && (
              <AssetsGlobalView tasks={snapshot.tasks} onSelectTask={(task) => setSelectedTaskId(task.id)} />
            )}
            {activeNav === 'ai' && (
              <AICenterView
                data={snapshot.providers}
                lead={snapshot.status.lead_ai || {}}
                onSave={async (values) => {
                  await updateAIConfig(values);
                  showToast('AI 配置已写入 Tiangong 后端');
                  await refresh(true);
                }}
                onProbe={async (id) => {
                  const result = await probeProvider(id);
                  showToast(String(result.detail || '探测完成'));
                  await refresh(true);
                }}
                onSaveKey={async (id, value) => {
                  await saveProviderKey(id, value);
                  showToast('API Key 已由后端安全存储');
                  await refresh(true);
                }}
                onClearKey={async (id) => {
                  await clearProviderKey(id);
                  showToast('后端已清除本地 Key');
                  await refresh(true);
                }}
              />
            )}
            {activeNav === 'nodes' && (
              <NodesGlobalView
                nodes={mapWorkers(snapshot.workers)}
                tools={snapshot.tools.tools || []}
                executionMode={String(snapshot.workers.execution_mode || 'local')}
                onProbe={async (id) => {
                  await probeWorker(id);
                  await refresh(true);
                }}
              />
            )}
            {activeNav === 'settings' && (
              <SettingsView
                settings={snapshot.settings}
                guard={snapshot.guard}
                tools={snapshot.tools}
                onAddScope={async (target) => {
                  await addScope(target);
                  showToast('授权范围已更新');
                  await refresh(true);
                }}
                onRemoveScope={async (target) => {
                  await removeScope(target);
                  showToast('授权范围已更新');
                  await refresh(true);
                }}
              />
            )}
          </>
        )}

        {toastMessage && (
          <div className="fixed bottom-6 right-6 z-50 bg-slate-900 border border-cyan-500/50 text-cyan-200 px-4 py-2.5 rounded-xl shadow-2xl text-xs font-mono">
            {toastMessage}
          </div>
        )}
      </main>

      <NewTaskModal
        isOpen={isNewTaskOpen}
        onClose={() => setIsNewTaskOpen(false)}
        onCreateTask={handleCreateTask}
      />
    </div>
  );
}
