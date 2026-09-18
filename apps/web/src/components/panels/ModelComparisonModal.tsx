"use client";

import { useEffect, useState } from "react";
import { BarChart3, X } from "lucide-react";

type Model = { id: string; name: string; inputs: string[]; csi: number; pod: number; far: number; trajectory_error_km: number; color: string };
type Report = { evaluation_type: string; disclaimer: string; horizons_minutes: number[]; models: Model[]; lead_time_csi: Record<string, number[]>; methodology: string[] };

interface ModelComparisonModalProps { open: boolean; onClose: () => void; }

export function ModelComparisonModal({ open, onClose }: ModelComparisonModalProps) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetch("/api/ml/ablation")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Model comparison is unavailable")))
      .then((payload: Report) => {
        if (cancelled) return;
        setReport(payload);
        setError(null);
      })
      .catch((reason: Error) => !cancelled && setError(reason.message));
    return () => { cancelled = true; };
  }, [open]);
  if (!open) return null;
  return <div className="absolute inset-0 z-50 flex items-center justify-center bg-slate-950/65 p-4 backdrop-blur-sm"><section role="dialog" aria-modal="true" className="max-h-[85vh] w-full max-w-4xl overflow-hidden rounded-2xl border border-slate-700 bg-[#0a0e27] shadow-2xl"><header className="flex items-start justify-between border-b border-slate-700 p-5"><div><h2 className="flex items-center gap-2 text-lg font-bold text-white"><BarChart3 className="h-5 w-5 text-violet-300" /> Multimodal ablation</h2><p className="mt-1 text-sm text-slate-400">Comparison of forecast skill by data-input configuration.</p></div><button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"><X className="h-6 w-6" /></button></header><div className="max-h-[68vh] overflow-y-auto p-5">{error && <p className="text-rose-200">{error}</p>}{!report && !error && <p className="text-slate-400">Loading comparison…</p>}{report && <><p className="mb-4 rounded border border-amber-400/20 bg-amber-400/5 p-3 text-xs text-amber-100">{report.disclaimer}</p><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-slate-700 text-xs uppercase text-slate-500"><tr><th className="pb-2">Model</th><th className="pb-2">CSI</th><th className="pb-2">POD</th><th className="pb-2">FAR ↓</th><th className="pb-2">Trajectory error ↓</th></tr></thead><tbody>{report.models.map((model) => <tr key={model.id} className="border-b border-slate-800"><td className="py-3"><div className="font-medium text-white">{model.name}</div><div className="mt-1 text-xs text-slate-500">{model.inputs.join(" + ")}</div></td><td className="py-3 font-mono" style={{ color: model.color }}>{(model.csi * 100).toFixed(0)}%</td><td className="py-3 font-mono text-slate-200">{(model.pod * 100).toFixed(0)}%</td><td className="py-3 font-mono text-slate-200">{(model.far * 100).toFixed(0)}%</td><td className="py-3 font-mono text-slate-200">{model.trajectory_error_km.toFixed(1)} km</td></tr>)}</tbody></table></div><div className="mt-6"><h3 className="mb-3 text-sm font-semibold text-white">CSI degradation by lead time</h3><div className="space-y-3">{report.models.map((model) => <div key={model.id}><div className="mb-1 flex justify-between text-xs"><span className="text-slate-300">{model.name}</span><span className="text-slate-500">{report.horizons_minutes.join(" · ")} min</span></div><div className="flex h-5 gap-1">{(report.lead_time_csi[model.id] ?? []).map((value, index) => <div key={index} title={`+${report.horizons_minutes[index]} min: ${(value * 100).toFixed(0)}%`} className="min-w-0 flex-1 rounded-sm" style={{ backgroundColor: model.color, opacity: Math.max(0.22, value), height: `${Math.max(35, value * 100)}%`, alignSelf: "end" }} />)}</div></div>)}</div></div><ul className="mt-6 list-disc space-y-1 pl-5 text-xs text-slate-400">{report.methodology.map((item) => <li key={item}>{item}</li>)}</ul></>}</div></section></div>;
}
