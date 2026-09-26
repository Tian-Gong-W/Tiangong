import React from 'react';
import { Layers, Server } from 'lucide-react';
import { AssetDomain } from '../../types';

interface AssetsTopologyTabProps {
  assetTree: AssetDomain;
  onViewFinding?: (findingId: string) => void;
}

export const AssetsTopologyTab: React.FC<AssetsTopologyTabProps> = ({ assetTree, onViewFinding }) => (
  <div className="max-w-6xl mx-auto space-y-4">
    <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3"><div><div className="text-xs text-slate-500">Mission target</div><div className="text-base font-bold font-mono mt-1">{assetTree.domain || '—'}</div></div><div className="text-xs text-slate-400">{assetTree.checkedHosts}/{assetTree.totalHosts} 个地址有扫描证据</div></div>
    {assetTree.hosts.length === 0 ? <div className="p-12 text-center rounded-2xl border border-dashed border-slate-700 text-sm text-slate-500"><Layers className="w-7 h-7 mx-auto mb-2" />尚无资产节点</div> : <div className="grid md:grid-cols-2 gap-3">{assetTree.hosts.map((host) => <div key={host.ip} className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800"><div className="flex justify-between"><span className="font-mono text-sm flex items-center gap-2"><Server className="w-4 h-4 text-cyan-400" />{host.ip}</span><span className="text-[10px] text-slate-400">{host.status}</span></div><div className="mt-4 space-y-2">{host.services.length ? host.services.map((service) => <div key={`${service.port}/${service.protocol}`} className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between"><span className="text-xs font-mono">{service.port}/{service.protocol} · {service.service}</span>{service.findingIds.length > 0 && <button onClick={() => onViewFinding?.(service.findingIds[0])} className="text-[10px] text-rose-300">{service.findingIds.length} findings</button>}</div>) : <div className="text-xs text-slate-500">无服务事实</div>}</div></div>)}</div>}
  </div>
);
