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
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("Model comparison is unavailable"))))
      .then((payload: Report) => {
        if (cancelled) return;
        setReport(payload);
        setError(null);
      })
      .catch((reason: Error) => !cancelled && setError(reason.message));
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-md">
      <section role="dialog" aria-modal="true" className="max-h-[85vh] w-full max-w-4xl flex flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#080b16] shadow-2xl">
        <header className="flex items-start justify-between border-b border-white/10 p-5 bg-black/20 shrink-0">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-bold text-white tracking-wide">
              <BarChart3 className="h-5 w-5 text-sky-400 drop-shadow-[0_0_8px_rgba(56,189,248,0.5)]" /> Multimodal Model Accuracy & Verification
            </h2>
            <p className="mt-1 text-xs font-medium text-slate-400">Comparison of nowcasting forecast skill across input configurations and lead times.</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/10 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="flex-1 min-h-0 overflow-y-auto p-6 space-y-6 no-scrollbar">
          {error && <p className="text-rose-400 font-medium">{error}</p>}
          {!report && !error && <p className="text-slate-400">Loading operational comparison metrics…</p>}
          {report && (
            <>
              <p className="rounded-xl border border-sky-500/20 bg-sky-500/10 p-4 text-xs font-medium text-sky-200 leading-relaxed shadow-sm">
                {report.disclaimer}
              </p>

              <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-900/60 p-4 shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-white/10 text-xs font-bold uppercase tracking-wider text-slate-400">
                    <tr>
                      <th className="pb-3">Model Architecture</th>
                      <th className="pb-3">CSI (Critical Success)</th>
                      <th className="pb-3">POD (Detection Prob)</th>
                      <th className="pb-3">FAR (False Alarm) ↓</th>
                      <th className="pb-3">Trajectory Error ↓</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {report.models.map((model) => (
                      <tr key={model.id} className="transition-colors hover:bg-white/5">
                        <td className="py-3.5 pr-4">
                          <div className="font-bold text-white">{model.name}</div>
                          <div className="mt-1 text-xs font-mono text-slate-400">{model.inputs.join(" + ")}</div>
                        </td>
                        <td className="py-3.5 font-mono font-bold" style={{ color: model.color }}>
                          {(model.csi * 100).toFixed(0)}%
                        </td>
                        <td className="py-3.5 font-mono text-slate-200">{(model.pod * 100).toFixed(0)}%</td>
                        <td className="py-3.5 font-mono text-slate-200">{(model.far * 100).toFixed(0)}%</td>
                        <td className="py-3.5 font-mono text-slate-200">{model.trajectory_error_km.toFixed(1)} km</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="rounded-xl border border-white/10 bg-slate-900/60 p-5 shadow-sm">
                <h3 className="mb-4 text-sm font-bold text-white tracking-wide">CSI Lead Time Skill Score Degradation</h3>
                <div className="space-y-4">
                  {report.models.map((model) => (
                    <div key={model.id}>
                      <div className="mb-1.5 flex justify-between text-xs font-semibold">
                        <span className="text-slate-200">{model.name}</span>
                        <span className="font-mono text-slate-400">{report.horizons_minutes.map((h) => `+${h}m`).join(" · ")}</span>
                      </div>
                      <div className="flex h-6 gap-1.5 rounded-lg bg-black/40 p-1 border border-white/5">
                        {(report.lead_time_csi[model.id] ?? []).map((value, index) => (
                          <div
                            key={index}
                            title={`+${report.horizons_minutes[index]} min lead time: ${(value * 100).toFixed(0)}% CSI`}
                            className="min-w-0 flex-1 rounded transition-all duration-300 flex items-center justify-center text-[10px] font-mono font-bold text-white"
                            style={{
                              backgroundColor: model.color,
                              opacity: Math.max(0.4, value),
                            }}
                          >
                            {(value * 100).toFixed(0)}%
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-white/5 bg-white/5 p-4 space-y-2">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-400">Evaluation Methodology & Verification</div>
                <ul className="list-disc space-y-1.5 pl-5 text-xs text-slate-300">
                  {report.methodology.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
