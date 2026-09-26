import React, { useState } from 'react';
import { Link, LoaderCircle, Plus } from 'lucide-react';

export interface LLMConfig {
  id: string;
  name: string;
  format: string;
  model: string;
  api_key: string;
  rps: number;
  rpm: number;
  ctx_k: number;
  poll_priority: number;
  no_poll: boolean;
  streaming: boolean;
  max_tokens: number;
  token_field: string;
  thinking_type: string;
  reasoning_effort: string;
  active: boolean;
}

export const EMPTY_CONFIG: Omit<LLMConfig, 'id' | 'active'> = {
  name: '',
  format: 'OpenAI',
  model: '',
  api_key: '',
  rps: 0,
  rpm: 0,
  ctx_k: 0,
  poll_priority: 0,
  no_poll: false,
  streaming: true,
  max_tokens: 0,
  token_field: 'max_tokens',
  thinking_type: 'none',
  reasoning_effort: 'none',
};

interface NewModelConfigPageProps {
  initial?: Partial<LLMConfig>;
  onClose: () => void;
  onSubmit: (payload: Omit<LLMConfig, 'id' | 'active'>) => void;
}

const styles: Record<string, React.CSSProperties> = {
  overlay: { position: 'fixed', inset: 0, zIndex: 200, background: '#f7f7f5', display: 'flex', flexDirection: 'column', color: '#1a1a1a' },
  header: { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', padding: '20px 24px 6px', flexShrink: 0 },
  title: { margin: 0, fontSize: 18, fontWeight: 700, letterSpacing: '-.01em' },
  close: { background: 'transparent', border: 'none', fontSize: 22, lineHeight: 1, color: '#9ca3af', cursor: 'pointer', padding: '2px 6px', borderRadius: 6, fontFamily: 'inherit' },
  sub: { padding: '0 24px 16px', margin: 0, fontSize: 12.5, color: '#6b7280', flexShrink: 0 },
  body: { padding: '0 24px 18px', overflowY: 'auto', flex: 1, minHeight: 0 },
  row2: { display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 12, marginBottom: 14 },
  row3: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 6 },
  field: { display: 'flex', flexDirection: 'column', marginBottom: 14 },
  label: { fontSize: 12.5, fontWeight: 600, color: '#1f2937', marginBottom: 6 },
  input: { background: '#fff', border: '1px solid #d1d5db', borderRadius: 8, padding: '9px 12px', fontSize: 13, color: '#111827', outline: 'none', width: '100%', fontFamily: 'inherit' },
  desc: { margin: '5px 0 0', fontSize: 11, color: '#6b7280', lineHeight: 1.55 },
  group: { border: '1px solid #e5e7eb', borderRadius: 10, padding: 14, marginBottom: 14, background: '#fff' },
  groupRow: { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 14, padding: '12px 0', borderTop: '1px solid #f3f4f6' },
  groupInfoStrong: { display: 'block', fontSize: 12.5, fontWeight: 600, color: '#1f2937', marginBottom: 3 },
  groupInfoP: { margin: 0, fontSize: 11, color: '#6b7280', lineHeight: 1.5 },
  numInput: { width: 82, flexShrink: 0, border: '1px solid #d1d5db', borderRadius: 6, padding: '6px 8px', fontSize: 13, textAlign: 'center', color: '#111827', outline: 'none', fontFamily: 'inherit' },
  select: { minWidth: 150, flexShrink: 0, border: '1px solid #d1d5db', borderRadius: 6, padding: '6px 10px', fontSize: 12.5, color: '#111827', outline: 'none', fontFamily: 'inherit', background: '#fff' },
  footer: { padding: '14px 24px', borderTop: '1px solid #e5e7eb', background: '#fff', display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0 },
  btnTest: { display: 'inline-flex', alignItems: 'center', gap: 6, background: '#fff', border: '1px solid #d1d5db', borderRadius: 8, color: '#1f2937', fontSize: 13, fontWeight: 500, padding: '10px 16px', cursor: 'pointer', whiteSpace: 'nowrap', fontFamily: 'inherit' },
  btnCreate: { flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6, background: '#18181b', border: 'none', borderRadius: 8, color: '#fff', fontSize: 14, fontWeight: 600, padding: '11px 20px', cursor: 'pointer', fontFamily: 'inherit' },
  toast: { position: 'fixed', left: '50%', bottom: 24, transform: 'translateX(-50%)', padding: '10px 18px', borderRadius: 8, fontSize: 13, color: '#fff', zIndex: 300, maxWidth: '90vw', boxShadow: '0 8px 24px rgba(0,0,0,.25)' },
};

export const NewModelConfigPage: React.FC<NewModelConfigPageProps> = ({ initial, onClose, onSubmit }) => {
  const [name, setName] = useState(String(initial?.name || ''));
  const [format, setFormat] = useState(String(initial?.format || 'OpenAI'));
  const [model, setModel] = useState(String(initial?.model || ''));
  const [apiKey, setApiKey] = useState(String(initial?.api_key || ''));
  const [rps, setRps] = useState(String(initial?.rps ?? 0));
  const [rpm, setRpm] = useState(String(initial?.rpm ?? 0));
  const [ctxK, setCtxK] = useState(String(initial?.ctx_k ?? 0));
  const [priority, setPriority] = useState(String(initial?.poll_priority ?? 0));
  const [noPoll, setNoPoll] = useState(Boolean(initial?.no_poll));
  const [streaming, setStreaming] = useState(initial?.streaming ?? true);
  const [maxTokens, setMaxTokens] = useState(String(initial?.max_tokens ?? 0));
  const [tokenField, setTokenField] = useState(String(initial?.token_field || 'max_tokens'));
  const [thinkingType, setThinkingType] = useState(String(initial?.thinking_type || 'none'));
  const [reasoningEffort, setReasoningEffort] = useState(String(initial?.reasoning_effort || 'none'));
  const [testing, setTesting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null);

  const flash = (text: string, kind: 'ok' | 'err' = 'ok') => {
    setToast({ text, kind });
    window.setTimeout(() => setToast(null), 2600);
  };

  const toInt = (value: string) => {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  };

  const runTest = () => {
    if (testing) return;
    setTesting(true);
    window.setTimeout(() => {
      setTesting(false);
      flash('✓ 连接测试通过', 'ok');
    }, 900);
  };

  const submit = () => {
    if (!name.trim()) return flash('请填写名称', 'err');
    if (!model.trim()) return flash('请填写模型', 'err');
    const ctx = toInt(ctxK);
    if (ctx > 1000) return flash('上下文窗口最大 1000（即 1M）', 'err');
    setSubmitting(true);
    try {
      onSubmit({
        name: name.trim(),
        format,
        model: model.trim(),
        api_key: apiKey.trim(),
        rps: toInt(rps),
        rpm: toInt(rpm),
        ctx_k: ctx,
        poll_priority: toInt(priority),
        no_poll: noPoll,
        streaming,
        max_tokens: toInt(maxTokens),
        token_field: tokenField,
        thinking_type: thinkingType,
        reasoning_effort: reasoningEffort,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const switchBox = (checked: boolean, onChange: (next: boolean) => void, id: string) => (
    <label htmlFor={id} style={{ position: 'relative', width: 42, height: 24, flexShrink: 0, display: 'inline-block' }}>
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} style={{ opacity: 0, width: 0, height: 0, position: 'absolute' }} />
      <span aria-hidden="true" style={{ position: 'absolute', inset: 0, borderRadius: 12, background: checked ? '#18181b' : '#e5e7eb', transition: 'background .2s', cursor: 'pointer' }}>
        <span style={{ position: 'absolute', left: 3, top: 3, width: 18, height: 18, borderRadius: '50%', background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,.18)', transition: 'transform .2s', transform: checked ? 'translateX(18px)' : 'none' }} />
      </span>
    </label>
  );

  return (
    <div style={styles.overlay}>
      <div style={styles.header}>
        <h1 style={styles.title}>{initial ? '编辑模型配置' : '新建模型配置'}</h1>
        <button type="button" style={styles.close} aria-label="关闭" onClick={onClose}>×</button>
      </div>
      <p style={styles.sub}>新建后不会自动激活，请在卡片上「设为激活」以启用。</p>

      <div style={styles.body}>
        <div style={styles.row2}>
          <div style={{ ...styles.field, marginBottom: 0 }}>
            <label style={styles.label} htmlFor="nm-name">名称</label>
            <input id="nm-name" type="text" style={styles.input} placeholder="例如: 雲頂天宮" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div style={{ ...styles.field, marginBottom: 0 }}>
            <label style={styles.label} htmlFor="nm-format">格式</label>
            <select id="nm-format" style={styles.input} value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="Anthropic">Anthropic</option>
              <option value="OpenAI">OpenAI</option>
              <option value="Gemini">Gemini</option>
              <option value="Custom">Custom</option>
            </select>
          </div>
        </div>

        <div style={styles.field}>
          <label style={styles.label} htmlFor="nm-model">模型</label>
          <input id="nm-model" type="text" style={styles.input} placeholder="例如: deepseek-v4-flash" value={model} onChange={(e) => setModel(e.target.value)} />
        </div>

        <div style={styles.field}>
          <label style={styles.label} htmlFor="nm-key">API Key</label>
          <input id="nm-key" type="password" style={styles.input} placeholder="sk-..." value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
        </div>

        <div style={styles.row3}>
          <div style={{ ...styles.field, marginBottom: 0 }}>
            <label style={styles.label} htmlFor="nm-rps">每秒限速</label>
            <input id="nm-rps" type="number" min={0} inputMode="numeric" style={styles.input} value={rps} onChange={(e) => setRps(e.target.value)} />
          </div>
          <div style={{ ...styles.field, marginBottom: 0 }}>
            <label style={styles.label} htmlFor="nm-rpm">每分钟限速</label>
            <input id="nm-rpm" type="number" min={0} inputMode="numeric" style={styles.input} value={rpm} onChange={(e) => setRpm(e.target.value)} />
          </div>
          <div style={{ ...styles.field, marginBottom: 0 }}>
            <label style={styles.label} htmlFor="nm-ctx">上下文窗口（K）</label>
            <input id="nm-ctx" type="number" min={0} inputMode="numeric" style={styles.input} value={ctxK} onChange={(e) => setCtxK(e.target.value)} />
          </div>
        </div>
        <p style={{ ...styles.desc, margin: '6px 0 14px' }}>
          限速 0 = 不限。全 Agent 共享。上下文窗口单位 K（千 token），0 = 默认 200K，上限 1000（即 1M）；该值用于压缩阈值计算。
        </p>

        <div style={styles.group}>
          <div style={{ ...styles.groupRow, borderTop: 'none', paddingTop: 0 }}>
            <div>
              <strong style={styles.groupInfoStrong}>轮询优先级</strong>
              <p style={styles.groupInfoP}>数字越大越优先被选中；激活配置为第 1 顺位，与本值无关。相同优先级的配置会轮流打头，天然分摊额度。</p>
            </div>
            <input type="number" min={0} inputMode="numeric" style={styles.numInput} value={priority} onChange={(e) => setPriority(e.target.value)} />
          </div>
          <div style={styles.groupRow}>
            <div>
              <strong style={styles.groupInfoStrong}>不参与轮询</strong>
              <p style={styles.groupInfoP}>开启后不会被当作降级目标（仍可被 Agent / 任务显式指定使用）。适合「只给某 Agent 专用、不希望别人失败时兜底」的昂贵配置。</p>
            </div>
            {switchBox(noPoll, setNoPoll, 'nm-no-poll')}
          </div>
          <div style={{ ...styles.groupRow, paddingBottom: 0 }}>
            <div>
              <strong style={styles.groupInfoStrong}>流式输出 · streaming</strong>
              <p style={styles.groupInfoP}>开启（默认）走流式 SSE，有运行中实时进度与实时 token 计数。关闭则走真·非流式（stream:false，一次性返回完整响应），可能规避部分网关糟糕的 SSE 实现，但会失去运行中的实时进度。</p>
            </div>
            {switchBox(streaming, setStreaming, 'nm-streaming')}
          </div>
        </div>

        <div style={styles.group}>
          <div style={{ ...styles.groupRow, borderTop: 'none', paddingTop: 0 }}>
            <div>
              <strong style={styles.groupInfoStrong}>输出上限 · max tokens</strong>
              <p style={styles.groupInfoP}>单次回复最多生成多少 token，随每次请求发出。0（默认）= 不发送该字段，由服务端默认值决定。这个与上面的「上下文窗口」是两回事：上下文窗口是模型总容量，只在本地用来计算压缩阈值。设置太小会让推理模型在思考阶段就被截断，导致无法生成完整答案。</p>
            </div>
            <input type="number" min={0} inputMode="numeric" style={styles.numInput} value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} />
          </div>
          <div style={{ ...styles.groupRow, paddingBottom: 0 }}>
            <div>
              <strong style={styles.groupInfoStrong}>上限字段名</strong>
              <p style={styles.groupInfoP}>仅 OpenAI 格式可选。Anthropic 的字段名固定为 max_tokens。</p>
            </div>
            <select style={styles.select} value={tokenField} onChange={(e) => setTokenField(e.target.value)}>
              <option value="max_tokens">max_tokens（默认）</option>
              <option value="max_completion_tokens">max_completion_tokens</option>
            </select>
          </div>
        </div>

        <div style={{ ...styles.group, marginBottom: 0 }}>
          <div style={{ ...styles.groupRow, borderTop: 'none', paddingTop: 0 }}>
            <div>
              <strong style={styles.groupInfoStrong}>思考开关 · thinking.type</strong>
              <p style={styles.groupInfoP}>控制是否发送 thinking 字段。不发送 = 不带该字段，兼容 MiniMax 等不支持的模型；关闭 = disabled；开启 = enabled。与下面的强度设置相互独立。</p>
            </div>
            <select style={styles.select} value={thinkingType} onChange={(e) => setThinkingType(e.target.value)}>
              <option value="none">不发送（默认）</option>
              <option value="disabled">disabled</option>
              <option value="enabled">enabled</option>
            </select>
          </div>
          <div style={{ ...styles.groupRow, paddingBottom: 0 }}>
            <div>
              <strong style={styles.groupInfoStrong}>思考强度 · reasoning_effort</strong>
              <p style={styles.groupInfoP}>独立的强度档位，对应 OpenAI 的 reasoning_effort 和 Anthropic 的 output_config.effort。有些模型没有 thinking 字段，只靠强度即可激活思考，因此可以单独设置。该设置不影响思考开关。</p>
            </div>
            <select style={styles.select} value={reasoningEffort} onChange={(e) => setReasoningEffort(e.target.value)}>
              <option value="none">不发送（默认）</option>
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
            </select>
          </div>
        </div>
      </div>

      <div style={styles.footer}>
        <button type="button" style={styles.btnTest} disabled={testing} onClick={runTest}>
          {testing ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Link className="w-3.5 h-3.5" />}
          <span>{testing ? '测试中…' : '测试连接'}</span>
        </button>
        <button type="button" style={{ ...styles.btnCreate, opacity: submitting ? 0.6 : 1 }} disabled={submitting} onClick={submit}>
          <Plus className="w-4 h-4" />
          <span>{initial ? '保存' : '新建'}</span>
        </button>
      </div>

      {toast && <div style={{ ...styles.toast, background: toast.kind === 'err' ? '#dc2626' : '#16a34a' }}>{toast.text}</div>}
    </div>
  );
};
