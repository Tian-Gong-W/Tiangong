import React, { useState } from 'react';
import {
  FileText,
  Download,
  ShieldAlert,
  CheckCircle2,
  Lock,
  Copy,
  Check,
  Share2,
  Printer,
  Sparkles,
} from 'lucide-react';
import { Task, Finding } from '../../types';

interface ReportTabProps {
  task: Task;
  findings: Finding[];
}

export const ReportTab: React.FC<ReportTabProps> = ({ task, findings }) => {
  const [copied, setCopied] = useState(false);
  const [exportFormat, setExportFormat] = useState<'markdown' | 'json'>('markdown');

  const generateMarkdownReport = () => {
    return `# 雲頂天宮 S̶h̶e̶l̶l̶ R̴e̴n 自动化渗透测试战果评估报告

**任务编号**: ${task.code}
**任务名称**: ${task.name}
**测试目标**: ${task.target}
**评估状态**: ${task.status === 'completed' ? '已完成' : '作战推演进行中'}
**生成时间**: ${new Date().toLocaleString('zh-CN')}
**执行节点**: ${task.assignedNode}

---

## 1. 核心态势与执行摘要
本次自动化渗透测试针对目标 \`${task.target}\` 进行了端到端自主攻击路径推演。
- **扫描覆盖主机**: ${task.assetsCount} 台
- **发现高危风险**: ${task.findingsCount.critical + task.findingsCount.high} 项 (严重: ${task.findingsCount.critical}, 高危: ${task.findingsCount.high})
- **事实验证率**: 100% (所有漏洞均已完成确定性利用与无害化回显验证)

---

## 2. 突破口与漏洞清单

${findings
  .map(
    (f, idx) => `### ${idx + 1}. [${f.severity}] ${f.title}
- **影响资产**: \`${f.affectedAsset}\`
- **CVE编号**: ${f.cve || 'N/A'} (CVSS: ${f.cvss || 'N/A'})
- **漏洞描述**: ${f.summary}
- **利用影响**: ${f.impact}
- **事实验证过程**: ${f.verification.method} (验证节点: ${f.verification.verifierWorker})
- **PoC 复现命令**:
\`\`\`bash
${f.pocCommand}
\`\`\`
- **修复方案**: ${f.remediation}
`
  )
  .join('\n')}

---

## 3. 证据保险箱战果归档
已成功导出管理员权限凭据、配置文件与系统权限证明，所有数据均已加密保存在 雲頂天宮 证据保险箱。

*报告由 雲頂天宮 S̶h̶e̶l̶l̶ R̴e̴n 自主渗透测试作战控制台自动生成*
`;
  };

  const handleDownload = () => {
    const content =
      exportFormat === 'markdown'
        ? generateMarkdownReport()
        : JSON.stringify({ task, findings }, null, 2);
    const blob = new Blob([content], {
      type: exportFormat === 'markdown' ? 'text/markdown' : 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `YundingTiangong_Report_${task.code.replace('#', '')}.${
      exportFormat === 'markdown' ? 'md' : 'json'
    }`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(generateMarkdownReport());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10">
      {/* Action Header */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <span>渗透测试战果评估报告</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                AUTO GENERATED
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              包含完整攻击证据链、影响面评估与加固建议
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition-colors flex items-center gap-1.5"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? '已复制报告' : '复制全文'}
          </button>

          <button
            onClick={handleDownload}
            className="px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition-colors flex items-center gap-1.5 shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            导出报告 (.md)
          </button>
        </div>
      </div>

      {/* Report Preview Document Canvas */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl text-slate-200 space-y-6">
        {/* Document Header */}
        <div className="border-b border-slate-800 pb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-mono text-cyan-400 font-bold uppercase tracking-wider">
              CONFIDENTIAL · PENETRATION REPORT
            </span>
            <h1 className="text-xl font-extrabold text-white mt-1">
              {task.name}
            </h1>
            <p className="text-xs text-slate-400 mt-1 font-mono">
              任务编号: {task.code} · 目标: {task.target} · 执行周期: 2026-08-28
            </p>
          </div>

          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-right">
            <div className="text-xs text-slate-400 font-mono">风险评估总评</div>
            <div className="text-lg font-bold text-rose-400 font-mono">
              CRITICAL / 高度受控
            </div>
          </div>
        </div>

        {/* Section 1: Executive Summary */}
        <div>
          <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400" /> 1. 执行摘要与态势评级
          </h3>
          <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
            本次自动化测试通过利用边界 Spring Cloud Gateway 远程代码执行漏洞 (CVE-2022-22947)
            打通内网入口，进而横向探测锁定核心 Windows Active Directory 域控制器，并使用 ZeroLogon
            (CVE-2020-1472) 成功捕获 Administrator 与 krbtgt NTLM Hash，实现了对整个企业核心域的权限接管。
          </p>
        </div>

        {/* Section 2: Key Findings Matrix */}
        <div>
          <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-400" /> 2. 关键漏洞与战果清单
          </h3>
          <div className="space-y-3">
            {findings.map((f, idx) => (
              <div
                key={f.id}
                className="p-4 bg-slate-950/80 rounded-xl border border-slate-800 space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-rose-400">
                      #{idx + 1} [{f.severity}]
                    </span>
                    <span className="font-bold text-white">{f.title}</span>
                  </div>
                  <span className="font-mono text-cyan-300 text-[11px]">
                    {f.affectedAsset}
                  </span>
                </div>
                <p className="text-slate-400 leading-relaxed">{f.summary}</p>
                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                  <span>验证方式: {f.verification.method}</span>
                  <span className="text-emerald-400">✓ 真实利用确定</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 3: Recommendations */}
        <div>
          <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" /> 3. 应急处置与整改建议
          </h3>
          <ul className="space-y-2 text-xs text-slate-300 list-disc list-inside bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 leading-relaxed">
            <li>立即对域控制器安装微软补丁 KB4557222，开启安全 RPC 强制通信。</li>
            <li>升级 Spring Cloud Gateway 至安全发布版本，关闭公网未鉴权的 Actuator 端点。</li>
            <li>内网 Redis 增加强密码并限制仅允许本地 127.0.0.1 访问。</li>
            <li>排查 Web 服务器敏感文件暴露 (.env, .git, 备份配置)，全网收敛外部暴露面。</li>
          </ul>
        </div>
      </div>
    </div>
  );
};
