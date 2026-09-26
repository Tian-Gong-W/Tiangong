import React, { useEffect, useState } from 'react';
import { Plus, Shuffle, Star, Trash2 } from 'lucide-react';
import { LLMConfig, NewModelConfigPage } from './NewModelConfigPage';

const STORAGE_KEY = 'tonmen.llm_configs';

function loadConfigs(): LLMConfig[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persist(configs: LLMConfig[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(configs));
}

function newId() {
  return 'llm_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

function keyMask(key: string) {
  if (!key) return '未配置';
  const tail = key.slice(-4);
  return '•••' + tail;
}

function thinkingText(config: LLMConfig) {
  if (config.thinking_type && config.thinking_type !== 'none') return config.thinking_type;
  if (config.reasoning_effort && config.reasoning_effort !== 'none') return config.reasoning_effort;
  return '默认';
}

const s: Record<string, React.CSSProperties> = {
  wrap: { background: '#faf9f6', borderRadius: 16, padding: '20px 22px', border: '1px solid #ece9e2', color: '#1a1a1a' },
  head: { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 18 },
  title: { margin: 0, fontSize: 20, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8 },
  subtitle: { margin: '6px 0 0', fontSize: 12.5, color: '#6b7280' },
  headActions: { display: 'flex', gap: 10, flexShrink: 0 },
  btnGhost: { display: 'inline-flex', alignItems: 'center', gap: 6, background: '#fff', border: '1px solid #e2ded5', borderRadius: 9, padding: '9px 14px', fontSize: 13, fontWeight: 600, color: '#333', cursor: 'pointer', fontFamily: 'inherit' },
  btnPrimary: { display: 'inline-flex', alignItems: 'center', gap: 6, background: '#18181b', border: '1px solid #18181b', borderRadius: 9, padding: '9px 16px', fontSize: 13, fontWeight: 700, color: '#fff', cursor: 'pointer', fontFamily: 'inherit' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(292px, 1fr))', gap: 14 },
  card: { background: '#fff', border: '1px solid #ece9e2', borderRadius: 14, padding: 16, display: 'flex', flexDirection: 'column', gap: 12, cursor: 'pointer', transition: 'box-shadow .15s, border-color .15s' },
  cardActive: { background: '#fdf8e7', border: '1px solid #f0e2b0' },
  cardTop: { display: 'flex', alignItems: 'center', gap: 8 },
  star: { background: 'transparent', border: 'none', padding: 0, cursor: 'pointer', display: 'inline-flex', lineHeight: 1 },
  name: { fontSize: 14.5, fontWeight: 700, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  chipFormat: { fontSize: 10, fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', border: '1px solid #d8d4ca', borderRadius: 5, padding: '2px 7px', color: '#4b5563' },
  chipStatus: { fontSize: 10.5, fontWeight: 700, color: '#16803c', background: '#e7f5ec', borderRadius: 6, padding: '3px 8px' },
  model: { fontSize: 12.5, color: '#4b5563', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  stats: { fontSize: 11.5, color: '#8a8578', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' },
  actions: { display: 'flex', gap: 8, alignItems: 'center' },
  btnActivate: { flex: 1, background: '#fff', border: '1px solid #e2ded5', borderRadius: 9, padding: '9px 12px', fontSize: 13, fontWeight: 600, color: '#333', cursor: 'pointer', fontFamily: 'inherit' },
  btnActivated: { flex: 1, background: '#f6edcf', border: '1px solid #eadfae', borderRadius: 9, padding: '9px 12px', fontSize: 13, fontWeight: 700, color: '#8a6d1a', cursor: 'default', fontFamily: 'inherit' },
  trash: { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 38, height: 38, background: '#fff', border: '1px solid #f0d6d6', borderRadius: 9, color: '#d64545', cursor: 'pointer', flexShrink: 0 },
  empty: { padding: '40px 20px', textAlign: 'center', color: '#9a958a', fontSize: 13, border: '1px dashed #ddd8cc', borderRadius: 14 },
  modalOverlay: { position: 'fixed', inset: 0, zIndex: 210, background: 'rgba(0,0,0,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 },
  modal: { width: 'min(560px,94vw)', maxHeight: '86vh', overflowY: 'auto', background: '#fff', borderRadius: 14, padding: 20, color: '#1a1a1a' },
  modalTitle: { margin: '0 0 4px', fontSize: 16, fontWeight: 700 },
  modalSub: { margin: '0 0 14px', fontSize: 12, color: '#6b7280' },
  pollRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 0', borderTop: '1px solid #f1efe9' },
  pollNum: { width: 78, border: '1px solid #d8d4ca', borderRadius: 7, padding: '6px 8px', fontSize: 13, textAlign: 'center', fontFamily: 'inherit' },
  pollInfo: { minWidth: 0 },
  pollName: { fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  pollMeta: { fontSize: 11, color: '#8a8578', marginTop: 2 },
  modalActions: { display: 'flex', justifyContent: 'flex-end', marginTop: 16 },
};

export const LLMConfigView: React.FC = () => {
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [editing, setEditing] = useState<LLMConfig | null>(null);
  const [creating, setCreating] = useState(false);
  const [pollOpen, setPollOpen] = useState(false);

  useEffect(() => {
    setConfigs(loadConfigs());
  }, []);

  const update = (next: LLMConfig[]) => {
    setConfigs(next);
    persist(next);
  };

  const handleCreate = (payload: Omit<LLMConfig, 'id' | 'active'>) => {
    const next = [...configs, { ...payload, id: newId(), active: false }];
    update(next);
    setCreating(false);
  };

  const handleEditSave = (payload: Omit<LLMConfig, 'id' | 'active'>) => {
    if (!editing) return;
    update(configs.map((item) => (item.id === editing.id ? { ...item, ...payload } : item)));
    setEditing(null);
  };

  const activate = (id: string) => {
    update(configs.map((item) => ({ ...item, active: item.id === id })));
  };

  const remove = (id: string) => {
    update(configs.filter((item) => item.id !== id));
  };

  const setPriority = (id: string, value: number) => {
    update(configs.map((item) => (item.id === id ? { ...item, poll_priority: value } : item)));
  };

  const toggleNoPoll = (id: string) => {
    update(configs.map((item) => (item.id === id ? { ...item, no_poll: !item.no_poll } : item)));
  };

  return (
    <div style={s.wrap}>
      <div style={s.head}>
        <div>
          <h2 style={s.title}>LLM</h2>
          <p style={s.subtitle}>全 Agent 共享的格式 / 模型 / 限速配置。点击卡片编辑，星标为当前激活配置。</p>
        </div>
        <div style={s.headActions}>
          <button type="button" style={s.btnGhost} onClick={() => setPollOpen(true)}>
            <Shuffle className="w-4 h-4" />轮询配置
          </button>
          <button type="button" style={s.btnGhost} onClick={() => setCreating(true)}>
            <Plus className="w-4 h-4" />新建
          </button>
        </div>
      </div>

      {configs.length === 0 ? (
        <div style={s.empty}>还没有模型配置。点击右上角「新建」添加第一个。</div>
      ) : (
        <div style={s.grid}>
          {configs.map((config) => (
            <div
              key={config.id}
              style={{ ...s.card, ...(config.active ? s.cardActive : {}) }}
              onClick={() => setEditing(config)}
            >
              <div style={s.cardTop}>
                <button
                  type="button"
                  style={s.star}
                  title={config.active ? '当前激活' : '设为激活'}
                  onClick={(event) => { event.stopPropagation(); activate(config.id); }}
                >
                  <Star className="w-4 h-4" style={{ color: config.active ? '#e0a800' : '#c8c4ba' }} fill={config.active ? '#e0a800' : 'none'} />
                </button>
                <div style={s.name}>{config.name || '未命名'}</div>
                <span style={s.chipFormat}>{config.format}</span>
                <span style={s.chipStatus}>正常</span>
              </div>

              <div style={s.model}>{config.model || '—'}</div>
              <div style={s.stats}>
                {keyMask(config.api_key)}&nbsp;&nbsp;{config.rps}s / {config.rpm}/min&nbsp;&nbsp;思考 {thinkingText(config)}
              </div>

              <div style={s.actions}>
                {config.active ? (
                  <button type="button" style={s.btnActivated} disabled>已激活</button>
                ) : (
                  <button
                    type="button"
                    style={s.btnActivate}
                    onClick={(event) => { event.stopPropagation(); activate(config.id); }}
                  >
                    设为激活
                  </button>
                )}
                <button
                  type="button"
                  style={s.trash}
                  title="删除"
                  onClick={(event) => { event.stopPropagation(); remove(config.id); }}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {creating && <NewModelConfigPage onClose={() => setCreating(false)} onSubmit={handleCreate} />}
      {editing && (
        <NewModelConfigPage
          initial={editing}
          onClose={() => setEditing(null)}
          onSubmit={handleEditSave}
        />
      )}

      {pollOpen && (
        <div style={s.modalOverlay} onClick={() => setPollOpen(false)}>
          <div style={s.modal} onClick={(event) => event.stopPropagation()}>
            <h3 style={s.modalTitle}>轮询配置</h3>
            <p style={s.modalSub}>数字越大越优先被选中；相同优先级轮流打头。开启「不参与轮询」后不会被当作降级目标。</p>
            {configs.length === 0 && <div style={{ fontSize: 12.5, color: '#8a8578' }}>暂无配置。</div>}
            {configs.map((config) => (
              <div key={config.id} style={s.pollRow}>
                <div style={s.pollInfo}>
                  <div style={s.pollName}>{config.name || '未命名'} <span style={{ color: '#9a958a', fontWeight: 400 }}>· {config.format}</span></div>
                  <div style={s.pollMeta}>{config.model || '—'}</div>
                  <label style={{ fontSize: 11.5, color: '#6b7280', display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
                    <input type="checkbox" checked={config.no_poll} onChange={() => toggleNoPoll(config.id)} />不参与轮询
                  </label>
                </div>
                <input
                  type="number"
                  min={0}
                  style={s.pollNum}
                  value={config.poll_priority}
                  onChange={(event) => setPriority(config.id, Number.parseInt(event.target.value, 10) || 0)}
                />
              </div>
            ))}
            <div style={s.modalActions}>
              <button type="button" style={s.btnPrimary} onClick={() => setPollOpen(false)}>完成</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
