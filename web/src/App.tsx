/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { NavItemId, Task, Finding, AIModelConfig, ExecutionNode } from './types';
import {
  initialTasks,
  mockFindings,
  mockAIConfig,
  mockExecutionNodes,
} from './data/mockData';
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
import { InterventionModal } from './components/InterventionModal';
import { LaicaiBackground } from './components/BrandingAssets';
import { CoverLockScreen } from './components/CoverLockScreen';

export default function App() {
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [activeNav, setActiveNav] = useState<NavItemId>('dashboard');
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);

  // Core State
  const [tasks, setTasks] = useState<Task[]>(initialTasks);
  const [findings, setFindings] = useState<Finding[]>(mockFindings);
  const [aiConfig, setAiConfig] = useState<AIModelConfig>(mockAIConfig);
  const [nodes, setNodes] = useState<ExecutionNode[]>(mockExecutionNodes);

  // Modals State
  const [isNewTaskOpen, setIsNewTaskOpen] = useState(false);
  const [interventionTask, setInterventionTask] = useState<Task | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  // Approvals
  const handleApprove = (approvalId: string) => {
    setTasks((prev) =>
      prev.map((t) => {
        if (t.pendingApproval?.id === approvalId) {
          const updated: Task = {
            ...t,
            status: 'running',
            pendingApproval: undefined,
            currentAction: '已获指挥官授权放行，S̶h̶e̶l̶l̶ R̴e̴n 继续深入状态空间推演',
            currentStage: '横向移动',
            progress: Math.min(100, t.progress + 15),
          };
          if (selectedTask?.id === t.id) {
            setSelectedTask(updated);
          }
          return updated;
        }
        return t;
      })
    );
    showToast('已批准本任务扩大授权，S̶h̶e̶l̶l̶ R̴e̴n 恢复继续执行');
  };

  const handleReject = (approvalId: string) => {
    setTasks((prev) =>
      prev.map((t) => {
        if (t.pendingApproval?.id === approvalId) {
          const updated: Task = {
            ...t,
            status: 'running',
            pendingApproval: undefined,
            currentAction: '指挥官已拒绝跨网段指令，S̶h̶e̶l̶l̶ R̴e̴n 正在收敛探索路径',
          };
          if (selectedTask?.id === t.id) {
            setSelectedTask(updated);
          }
          return updated;
        }
        return t;
      })
    );
    showToast('已拒绝该敏感操作，S̶h̶e̶l̶l̶ R̴e̴n 将在既定安全边界内推演');
  };

  // Pause / Resume
  const handleTogglePause = (taskId: string) => {
    setTasks((prev) =>
      prev.map((t) => {
        if (t.id === taskId) {
          const newStatus = t.status === 'running' ? 'paused' : 'running';
          const updated: Task = {
            ...t,
            status: newStatus,
            currentAction:
              newStatus === 'paused' ? '任务已由指挥官手动暂停' : '恢复自主探测推演',
          };
          if (selectedTask?.id === t.id) {
            setSelectedTask(updated);
          }
          return updated;
        }
        return t;
      })
    );
  };

  // Terminate
  const handleTerminateTask = (taskId: string) => {
    setTasks((prev) =>
      prev.map((t) => {
        if (t.id === taskId) {
          const updated: Task = {
            ...t,
            status: 'completed',
            currentAction: '任务已由指挥官强制终止',
          };
          if (selectedTask?.id === t.id) {
            setSelectedTask(updated);
          }
          return updated;
        }
        return t;
      })
    );
    showToast('任务已强制终止归档');
  };

  // Create Task
  const handleCreateTask = (newTaskData: Partial<Task>) => {
    const newTask: Task = {
      id: `task-${Date.now()}`,
      name: newTaskData.name || '新建作战任务',
      code: newTaskData.code || `#Task-${Date.now().toString().slice(-6)}`,
      target: newTaskData.target || 'target.example.com',
      type: newTaskData.type || 'RedTeam',
      status: 'running',
      currentStage: '侦察与信息收集',
      currentAction: '正在初始化全端口扫描与指纹识别...',
      runtimeMinutes: 1,
      completedSteps: 1,
      totalSteps: 18,
      progress: 8,
      findingsCount: { critical: 0, high: 0, medium: 0, low: 0 },
      assetsCount: 1,
      assignedNode: 'Worker-Edge-01 (北京集群)',
      executionEvents: newTaskData.executionEvents || [],
      chainNodes: newTaskData.chainNodes || [],
      chainEdges: newTaskData.chainEdges || [],
      assetTree: newTaskData.assetTree || {
        id: `dom-${Date.now()}`,
        domain: newTaskData.target || '',
        scopeStatus: 'in_scope',
        totalHosts: 1,
        checkedHosts: 1,
        hosts: [],
      },
      startTime: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      nextAction: '进一步探测开放服务漏洞',
      actionRequired: false,
      authorizedScope: [newTaskData.target || ''],
      reportReady: false,
    };

    setTasks([newTask, ...tasks]);
    setSelectedTask(newTask);
    showToast('新渗透作战任务已下发，作战室已就绪');
  };

  // Commander Intervention
  const handleIntervene = (taskId: string, directive: string) => {
    setTasks((prev) =>
      prev.map((t) => {
        if (t.id === taskId) {
          const newEvent = {
            id: `evt-intervene-${Date.now()}`,
            timeDisplay: new Date().toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            }),
            tool: 'Commander-CLI',
            target: t.target,
            title: `人工指令介入: ${directive.slice(0, 20)}...`,
            status: 'completed' as const,
            duration: '0s',
            outputSummary: `已采纳指挥官专家指令: "${directive}"`,
            rawOutput: `[HUMAN-IN-THE-LOOP] Directive injected into reasoning engine: ${directive}\n[AI] Re-evaluating attack path priorities...`,
            workerNode: 'Master-Orchestrator',
          };

          const updated: Task = {
            ...t,
            currentAction: `正在执行指挥官指令: ${directive.slice(0, 24)}...`,
            executionEvents: [...t.executionEvents, newEvent],
          };
          if (selectedTask?.id === t.id) {
            setSelectedTask(updated);
          }
          return updated;
        }
        return t;
      })
    );
    showToast('专家指令已注入 AI 推理链');
  };

  // Calculate approval count for sidebar badge
  const pendingApprovalsCount = tasks.filter(
    (t) => t.status === 'waiting_approval' && t.pendingApproval
  ).length;

  if (!isUnlocked) {
    return <CoverLockScreen onUnlock={() => setIsUnlocked(true)} />;
  }

  return (
    <div className="flex h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans relative">
      {/* Background with Faded Calligraphy / Gold Texture (Image 2) */}
      <LaicaiBackground />

      {/* 1. Global Shell V2 Navigation (Sidebar) */}
      <Sidebar
        activeNav={activeNav}
        onSelectNav={(id) => {
          setActiveNav(id);
          setSelectedTask(null); // Return from War Room to the chosen global view
        }}
        approvalsCount={pendingApprovalsCount}
        runningTasksCount={tasks.filter((t) => t.status === 'running').length}
        onLock={() => setIsUnlocked(false)}
      />

      {/* 2. Main Content Canvas */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
        {/* If a Task War Room is open, show the Task War Room */}
        {selectedTask ? (
          <TaskWarRoom
            task={selectedTask}
            allFindings={findings}
            onBack={() => setSelectedTask(null)}
            onTogglePause={handleTogglePause}
            onTerminateTask={handleTerminateTask}
            onApprove={handleApprove}
            onReject={handleReject}
            onOpenInterventionModal={(t) => setInterventionTask(t)}
          />
        ) : (
          <>
            {/* Global Views based on 7-item Navigation */}
            {activeNav === 'dashboard' && (
              <DashboardView
                tasks={tasks}
                findings={findings}
                onSelectTask={(task) => setSelectedTask(task)}
                onApprove={handleApprove}
                onReject={handleReject}
                onOpenNewTaskModal={() => setIsNewTaskOpen(true)}
                onNavigateFindings={() => setActiveNav('findings')}
              />
            )}

            {activeNav === 'tasks' && (
              <TasksListView
                tasks={tasks}
                onSelectTask={(task) => setSelectedTask(task)}
                onOpenNewTaskModal={() => setIsNewTaskOpen(true)}
                onTogglePause={handleTogglePause}
              />
            )}

            {activeNav === 'findings' && (
              <FindingsGlobalView
                findings={findings}
                onSelectFindingTask={(taskId) => {
                  const t = tasks.find((item) => item.id === taskId);
                  if (t) setSelectedTask(t);
                }}
              />
            )}

            {activeNav === 'assets' && (
              <AssetsGlobalView
                tasks={tasks}
                onSelectTask={(task) => setSelectedTask(task)}
              />
            )}

            {activeNav === 'ai' && (
              <AICenterView
                config={aiConfig}
                onUpdateConfig={(newConfig) => {
                  setAiConfig(newConfig);
                  showToast('AI 模型策略已更新');
                }}
              />
            )}

            {activeNav === 'nodes' && <NodesGlobalView nodes={nodes} />}

            {activeNav === 'settings' && <SettingsView />}
          </>
        )}

        {/* Global Toast Notification */}
        {toastMessage && (
          <div className="fixed bottom-6 right-6 z-50 bg-slate-900 border border-cyan-500/50 text-cyan-200 px-4 py-2.5 rounded-xl shadow-2xl text-xs font-mono flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            {toastMessage}
          </div>
        )}
      </main>

      {/* Modals */}
      <NewTaskModal
        isOpen={isNewTaskOpen}
        onClose={() => setIsNewTaskOpen(false)}
        onCreateTask={handleCreateTask}
      />

      <InterventionModal
        task={interventionTask}
        isOpen={!!interventionTask}
        onClose={() => setInterventionTask(null)}
        onSubmitIntervention={handleIntervene}
      />
    </div>
  );
}
