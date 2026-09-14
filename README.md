# 雲頂天宮 | Tiangong (TONMEN)

> **人予其意，宮成其事。**  
> **宮察其象，鑑明其實；天策既定，萬器乃行。**  
> **“權力不是靜態分配的，而是動態競爭出來的。”**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Platform: Web & CLI](https://img.shields.io/badge/Platform-Web%20%7C%20CLI-orange.svg)](https://topmen.one)
[![Autonomous Cyber Arena](https://img.shields.io/badge/Architecture-Cyber%20Combatant%20Arena-red.svg)](https://topmen.one)

**Tiangong（雲頂天宮 / TONMEN）** 是由 Top-Men AI 打造的**工业级自主赛博智能体竞技场与高对抗实战渗透中枢**。

它彻底颠覆了传统安全平台“人工写死模型、静态单选菜单、伪随机打分”的空壳形态，首次引入**概率攻击图（PAG）边际贡献客观锚定、多 LLM 战略家动态博弈竞聘总帅、子代理掠夺流转、临场肉搏突防与三大实战底座**，实现了由客观战场收益自主驱动的下一代自主安全运营体系。

---

## 核心哲学：动态竞争裁决 (Dynamic Competition over Static Allocation)

在真实的高对抗攻防中，单一模型必然存在认知盲区与战术幻觉。天工的核心理念在于：**没有永久的统帅，只有战果决定的权力。**

```text
       ┌──────────────────────────────────────────────────────────────┐
       │               概率攻击图 (Probabilistic Attack Graph)          │
       │   [资产侦察] ──(P=0.9)──> [WAF识别] ──(P=0.7)──> [WAF绕过] ───┐ │
       │       │                                             │   │
       │       └───(P=0.85)──> [服务漏洞] ───(P=0.75)──> [低权立足] ───┴─┼─(P=0.6)─> [核心特权]
       └──────────────────────────────────────────────────────────────┘
                                      ▲
                         实时只读快照 │  边际贡献 ΔP 结算
                                      │
 ┌────────────────────────────────────┴─────────────────────────────────────┐
 │                      The Arbiter 动态裁决核心                             │
 │  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────┐  │
 │  │ 理论准确度 (Accuracy)│  │ 执行成功率 (Success) │  │ 风险收益比(RR) │  │
 │  │      想得对不对      │  │      做得好不好      │  │    划不划算    │  │
 │  └──────────────────────┘  └──────────────────────┘  └────────────────┘  │
 │           ▲                           ▲                      ▲           │
 │           └───────────────────────────┼──────────────────────┘           │
 │                              三维量化评分综合排名                        │
 └───────────────────────────────────────┬──────────────────────────────────┘
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 ▼                       ▼                       ▼
       ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
       │ Claude 3.5 Sonnet │   │    DeepSeek-V3    │   │      GPT-4o       │
       │ (启发式状态空间搜索)│   │ (实战载荷与高转化)│   │ (广谱资产边缘探测)│
       │   配额: 3 代理    │   │   配额: 2 代理    │   │   配额: 4 代理    │
       └───────────────────┘   └───────────────────┘   └───────────────────┘
                 │                       ▲
                 └───────[ 败者掠夺 ]─────┘ (Looting Rule: 胜者掠夺末位子代理配额)
```

---

## 核心模块与技术实现

### 1. 概率攻击图与边际贡献引擎 (PAG & Marginal Progress $\Delta P$)
* **源码位置**：[`src/tonmen/arena/graph.py`](src/tonmen/arena/graph.py)
* **技术原理**：
  - 基于有向无环图（DAG）对网络渗透拓扑中的 `OR 节点`、`AND 节点` 与 `State 状态节点` 建模；
  - 动态规划拓扑正向传递，实时计算当前达成终极攻陷目标的条件概率 $P(Goal \mid G)$；
  - 任何战利品（Loot）发现时，依据达成节点的拓扑连通变化，精确计算该行动的**客观边际收益**：
    $$\Delta P = \max\Big(0, P(Goal \mid G \cup \{L\}) - P(Goal \mid G)\Big)$$
  - 彻底杜绝主观经验打分，所有评分与资源分配均建立在真实的攻防拓扑推进之上。

### 2. The Arbiter 三维裁判与博弈治理 (Command Shift & Looting)
* **源码位置**：[`src/tonmen/arena/arbiter.py`](src/tonmen/arena/arbiter.py) & [`src/tonmen/arena/ledger.py`](src/tonmen/arena/ledger.py)
* **三维评价指标**：
  1. **理论准确度 ($\mathcal{S}_{\text{theory}}$)**：提案前置条件在当前战场图的满足度与因果推导严密性（权重 35%）；
  2. **执行成功率 ($\mathcal{S}_{\text{exec}}$)**：底层执行单元（Worker）动作的有效转化率与闭环有效性（权重 35%）；
  3. **风险收益比 ($\mathcal{S}_{\text{rr}}$)**：边际进度收益 $\Delta P$ 与时间衰减、检测暴露风险及资源消耗的商（权重 30%）。
* **统帅权交接（Command Shift）**：某一战略家连续两轮综合得分领先现任统帅 $\ge 30\%$，系统触发即时换帅，移交战场总指挥权；每 50 轮执行一次全域纪元大洗牌。
* **子代理掠夺规则（The Looting Rule）**：单轮胜出战略家从末位模型掠夺 1 个子代理执行配额，并继承其有效战术参数；**严格采用跨模型会话隔离**，杜绝 Prompt 记忆污染。
* **自适应熔断（Circuit Breaker）**：全员低分或遇顽固防线时自愈进入高隐匿（Stealth）监听状态。

### 3. 多 LLM 战略家观察者池 (Strategist Observer Pool)
* **源码位置**：[`src/tonmen/arena/strategists.py`](src/tonmen/arena/strategists.py)
* **技术特性**：
  - 并发调度 Claude 3.5 Sonnet、DeepSeek-V3、GPT-4o 及 OpenRouter 模型集群（`asyncio.gather` 并行扇出）；
  - 向战略家输入只读图快照与实时 RAG 上下文，输出严谨格式的 `TacticalProposal` 结构体；
  - 配备 5.5s 自适应超时保护与快速启发式降级熔断，保证前端大屏实时推演流畅无卡顿。

### 4. 战术肉搏模式 (“亲自下场” Tactical Combat Mode)
* **技术特性**：
  - 战略家累积积分 $\ge 50$ 时，可消耗 50 点预算“亲自下场肉搏”，向核心防御节点发起定向高侵略性武器化突防；
  - 自动从实时安全知识库中检索专属现代化 TKO 绕过与利用规则；
  - 突防成功不仅解锁关键拓扑节点、产生边际收益 $\Delta P$，更斩获 $+120$ 点高额积分赏金；
  - 若突防带来边际增量 $\Delta P \ge 5\%$，直接触发临场换帅夺取总指挥权。

---

## 三大实战底座支撑 (The 3 Infrastructure Pillars)

为确保大模型在现代强防御网络环境下的持续生存与作战能力，天工配备了三大实战工业底座：

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      天工三大实战底座 (Infrastructure Pillars)          │
 ├─────────────────────────┬──────────────────────┬───────────────────────┤
 │ 1. 实时网络安全知识库   │ 2. 出口 IP 调度更替池│ 3. 会话令牌长效维持池 │
 │   (Live Knowledge Hub)  │   (Egress Manager)   │    (Session Vault)    │
 ├─────────────────────────┼──────────────────────┼───────────────────────┤
 │ • SQLite FTS5 全文索引  │ • 无状态探测动态轮换 │ • 统一托管 Token/Cookie│
 │ • 毫秒级 BM25 战术检索  │ • 鉴权动作 Sticky 会话│ • TTL 20% 自动刷新续期│
 │ • 自动注入现代 TKO 规则 │ • 429/403 节点降温熔断│ • 随机低频心跳防挂起  │
 └─────────────────────────┴──────────────────────┴───────────────────────┘
```

* **实时网络安全知识库**：[`src/tonmen/infrastructure/knowledge_hub.py`](src/tonmen/infrastructure/knowledge_hub.py)，采用 SQLite FTS5 引擎构建毫秒级 RAG 知识检索，让大模型在推演前汲取最新现代 WAF 绕过、协议走私与漏洞利用技术（TKO）；
* **出口 IP 调度更替池**：[`src/tonmen/infrastructure/egress_pool.py`](src/tonmen/infrastructure/egress_pool.py)，无状态动作高频轮换，认证动作启用 IP Sticky Session 绑定（防异地会话失效），节点遇 429/403 自动移入降温隔离池；
* **会话令牌长效维持池**：[`src/tonmen/infrastructure/session_vault.py`](src/tonmen/infrastructure/session_vault.py)，自动托管渗透过程中获取的 JWT/Cookie/API Key，当租期消耗达 80% 时自动触发 Refresh，并注入随机低频幽灵心跳避免服务端挂起失效。

---

## 181 攻防武器库与工具链适配 (Arsenal Adapters)

* **源码位置**：[`src/tonmen/tools/adapters/arsenal.py`](src/tonmen/tools/adapters/arsenal.py)
* **武器库接入**：
  - 将 `/home/wang/真心` 中包含的 181 个实战攻防脚本深度封装；
  - 核心适配模块：
    - `arsenal.sqli`: 包含布尔盲注、时间盲注与报错注入的全自动探测；
    - `arsenal.portscan`: 高并发异步端口扫描与 Banner 识别；
    - `arsenal.waf`: 深度识别 Cloudflare、Akamai、Imperva、ModSecurity 等防护指纹；
    - 外部经典工具链深度适配：`sqlmap`、`nuclei`、`katana`、`subfinder`；
  - 统一注册至 `ToolRegistry`，实现结构化参数构建与执行引擎强隔离（`shell=False`）。

---

## 快速安装与使用指南

### 环境要求
- Linux / macOS (推荐 Linux)
- Python **3.10+**
- Node.js **18+** (用于构建前端控制台)

### 1. 克隆与初始化

```bash
git clone https://github.com/Tian-Gong-W/Tiangong.git
cd Tiangong

# 创建 Python 虚拟环境
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e .
```

### 2. 配置大模型 API 密钥

天工内置完善的密文管理系统，配置文件位于 `~/.tonmen/secrets.json`：

```json
{
  "DEEPSEEK_API_KEY": "sk-your-deepseek-api-key",
  "OPENROUTER_API_KEY": "sk-or-v1-your-openrouter-key",
  "ANTHROPIC_API_KEY": "your-anthropic-key",
  "OPENAI_API_KEY": "your-openai-key"
}
```

### 3. 构建前端控制台 (Web Console)

```bash
cd web
npm install
npm run build
cd ..
```

### 4. 启动天工赛博竞技场中枢

通过生产守护服务启动 API 与 SSE 实时控制台：

```bash
export TONMEN_WEB_TOKEN="your_secure_master_token_2026"
export PORT=8899
export PYTHONPATH=src

python3 -m tonmen.web_server
```

启动后访问：`http://127.0.0.1:8899`，在界面中即可实时观看：
- 动态概率攻击图（PAG DAG）拓扑展开；
- 战略家实时积分天梯与三维量化雷达；
- 统帅权交接日志与子代理掠夺流转动画；
- 战略家亲自下场突防肉搏与赏金结算。

---

## 核心接口 (API References)

所有控制面 API 均支持 Bearer Token 认证：

| 端点 | 请求方法 | 说明 |
| :--- | :---: | :--- |
| `/api/arena/status` | `GET` | 获取当前攻击图、战略家账本、底座遥测的完整快照 |
| `/api/arena/stream` | `GET` (SSE) | 服务端事件流，毫秒级推送推演轮次、换帅与战果变化 |
| `/api/arena/simulate-round` | `POST` | 手动触发一轮多模型推演、裁决打分与指挥权结算 |
| `/api/arena/tactical-combat` | `POST` | 指定战略家消耗 50 积分亲自下场突防核心防御节点 |
| `/api/arena/auto-mode` | `POST` | 开启 / 关闭后台自主连续推演守护循环 |

---

## 自动化测试与质量保障

天工具备严格的测试覆盖标准，运行以下指令即可执行全部核心测试套件：

```bash
PYTHONPATH=src:. python3 -c "
import importlib
for m in ['tests.test_arena_arbiter_p1', 'tests.test_infrastructure_pillars', 'tests.test_arsenal_and_tactical_combat']:
    mod = importlib.import_module(m)
    for name in dir(mod):
        if name.startswith('test_'):
            getattr(mod, name)()
            print(f'✓ {m}.{name} passed')
"
```

**测试通过清单**：
- `test_probabilistic_graph_marginal_progress`: 拓扑图边际贡献 $\Delta P$ 动态递增与归一化验证
- `test_arbiter_3d_scoring_and_command_shift`: 三维打分、统帅权 30% 门限交接与子代理掠夺
- `test_live_security_knowledge_hub`: SQLite FTS5 全文索引毫秒级检索与知识入库
- `test_egress_manager_routing_and_cooldown`: 出口 IP 动态轮换、Sticky 绑定与熔断冷却
- `test_session_vault_lifecycle`: 会话凭证 80% TTL 自动续期与低频幽灵心跳保活
- `test_arsenal_adapters_and_registry`: 181 武器库与主流扫描工具统一参数构建
- `test_mission_arena_bridge`: 渗透任务实战发现与攻击图节点双向映射验证
- `test_tactical_combat_mode_and_knowledge_hub`: 亲自下场肉搏突防、TKO 情报检索与临场夺帅

---

## 免责声明 (Disclaimer)

天工（Tiangong / TONMEN）专为合规网络安全防御研究、授权渗透测试及红蓝攻防对抗演练而设计。使用者必须在获得明确书面授权的前提下对目标资产进行评估测试。严禁将本系统用于任何未授权入侵、破坏或非法攻击行为。
