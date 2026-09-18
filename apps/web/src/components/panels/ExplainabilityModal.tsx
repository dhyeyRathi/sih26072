"use client";

import { useEffect, useState } from "react";
import { Activity, BrainCircuit, X } from "lucide-react";

interface ExplainabilityModalProps {
  cellId: string | null;
  open: boolean;
  onClose: () => void;
}

type ExplainabilityResponse = {
  cell_id: string;
  synthesis?: string;
  data_quality?: string;
  indicators?: Record<string, Record<string, string | number | boolean | null>>;
  evidence?: string[];
};

const labels: Record<string, string> = {
  convective_instability: "Convective instability",
  radar_core_dynamics: "Radar core dynamics",
  satellite_microphysics: "Satellite microphysics",
  lightning_jump: "Lightning jump",
  kinematics: "Storm kinematics",
};

export function ExplainabilityModal({ cellId, open, onClose }: ExplainabilityModalProps) {
  const [data, setData] = useState<ExplainabilityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !cellId) return;
    let cancelled = false;
    fetch(`/api/explainability/${cellId}`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Warning evidence is unavailable")))
      .then((response: ExplainabilityResponse) => {
        if (cancelled) return;
        setData(response);
        setError(null);
      })
      .catch((reason: Error) => !cancelled && setError(reason.message));
    return () => { cancelled = true; };
  }, [cellId, open]);

  if (!open) return null;

  const currentData = data?.cell_id === cellId ? data : null;

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm">
      <section role="dialog" aria-modal="true" className="max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-2xl border border-slate-700 bg-[#0a0e27] shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-700 p-5"><div><h2 className="flex items-center gap-2 text-lg font-bold text-white"><BrainCircuit className="h-5 w-5 text-sky-300" /> Why is the system warning?</h2><p className="mt-1 text-sm text-slate-400">Cell {cellId ?? "—"} · physically grounded diagnostic evidence</p></div><button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"><X className="h-6 w-6" /></button></header>
        <div className="max-h-[68vh] overflow-y-auto p-5">
          {error && <p className="rounded border border-rose-400/30 bg-rose-500/10 p-3 text-rose-200">{error}</p>}
          {!error && !currentData && <p className="text-slate-400">Preparing meteorological evidence…</p>}
          {currentData && <>
            <div className="mb-5 rounded-xl border border-sky-400/20 bg-sky-400/5 p-4 text-sm leading-6 text-slate-200"><Activity className="mr-2 inline h-4 w-4 text-sky-300" />{currentData.synthesis ?? "No synthesis was returned."}</div>
            <div className="grid gap-3 md:grid-cols-2">{Object.entries(currentData.indicators ?? {}).map(([key, values]) => <div key={key} className="rounded-xl border border-slate-700 bg-slate-900/50 p-4"><h3 className="mb-3 text-sm font-semibold text-white">{labels[key] ?? key.replaceAll("_", " ")}</h3><dl className="space-y-1.5">{Object.entries(values).map(([name, value]) => <div key={name} className="flex justify-between gap-3 text-xs"><dt className="capitalize text-slate-400">{name.replaceAll("_", " ")}</dt><dd className="text-right font-mono text-sky-200">{String(value ?? "—")}</dd></div>)}</dl></div>)}</div>
            {currentData.evidence && currentData.evidence.length > 0 && <ul className="mt-5 space-y-1 text-sm text-slate-300">{currentData.evidence.map((item, index) => <li key={index}>• {item}</li>)}</ul>}
          </>}
        </div>
      </section>
    </div>
  );
}
