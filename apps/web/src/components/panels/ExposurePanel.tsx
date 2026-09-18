"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Building2, MapPin, Plane, Route, X } from "lucide-react";

type Asset = {
  id: string;
  name: string;
  category: string;
  lat: number;
  lon: number;
  district: string;
  threat_level: "critical" | "warning" | "watch" | "safe";
  estimated_arrival_minutes: number | null;
  distance_to_storm_km: number | null;
};

type ExposureResponse = {
  assets: Asset[];
  summary?: {
    critical_count?: number;
    warning_count?: number;
    estimated_exposed_population?: number;
    composite_exposure_score?: number;
  };
};

interface ExposurePanelProps {
  open: boolean;
  onClose: () => void;
  onFocus: (location: { lat: number; lon: number }) => void;
}

const threatStyles: Record<Asset["threat_level"], string> = {
  critical: "bg-rose-500/20 text-rose-300 border-rose-400/40",
  warning: "bg-orange-500/20 text-orange-300 border-orange-400/40",
  watch: "bg-amber-500/20 text-amber-300 border-amber-400/40",
  safe: "bg-emerald-500/15 text-emerald-300 border-emerald-400/30",
};

function AssetIcon({ category }: { category: string }) {
  if (category === "airport") return <Plane className="h-4 w-4" />;
  if (category === "highway") return <Route className="h-4 w-4" />;
  return <Building2 className="h-4 w-4" />;
}

export function ExposurePanel({ open, onClose, onFocus }: ExposurePanelProps) {
  const [data, setData] = useState<ExposureResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetch("/api/exposure/assets")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Exposure service unavailable")))
      .then((response: ExposureResponse) => {
        if (cancelled) return;
        setData(response);
        setError(null);
      })
      .catch((reason: Error) => !cancelled && setError(reason.message));
    return () => { cancelled = true; };
  }, [open]);

  if (!open) return null;

  const assets = data?.assets ?? [];
  const threatened = assets.filter((asset) => asset.threat_level !== "safe");

  return (
    <aside className="absolute left-4 top-16 z-40 flex max-h-[calc(100%-6rem)] w-[22rem] flex-col overflow-hidden rounded-xl border border-slate-700/70 bg-[#0a0e27]/95 shadow-2xl backdrop-blur-xl">
      <header className="flex items-start justify-between border-b border-slate-700/60 p-4">
        <div>
          <div className="flex items-center gap-2 font-bold text-white"><AlertTriangle className="h-5 w-5 text-amber-400" /> Exposure & assets</div>
          <p className="mt-1 text-xs text-slate-400">Forecast-path impact on critical Gujarat infrastructure.</p>
        </div>
        <button onClick={onClose} aria-label="Close exposure panel" className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"><X className="h-5 w-5" /></button>
      </header>

      {data?.summary && (
        <div className="grid grid-cols-3 gap-px border-b border-slate-700/60 bg-slate-700/60 text-center">
          <div className="bg-[#0a0e27] p-2"><div className="text-lg font-bold text-rose-300">{data.summary.critical_count ?? 0}</div><div className="text-[10px] uppercase text-slate-400">Critical</div></div>
          <div className="bg-[#0a0e27] p-2"><div className="text-lg font-bold text-orange-300">{data.summary.warning_count ?? 0}</div><div className="text-[10px] uppercase text-slate-400">Warning</div></div>
          <div className="bg-[#0a0e27] p-2"><div className="text-lg font-bold text-amber-200">{data.summary.composite_exposure_score ?? 0}</div><div className="text-[10px] uppercase text-slate-400">Score</div></div>
        </div>
      )}

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {error && <p className="rounded border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</p>}
        {!error && assets.length === 0 && <p className="p-3 text-sm text-slate-400">Loading critical infrastructure…</p>}
        {(threatened.length ? threatened : assets).map((asset) => (
          <button key={asset.id} onClick={() => onFocus({ lat: asset.lat, lon: asset.lon })} className="w-full rounded-lg border border-slate-700/60 bg-slate-800/50 p-3 text-left transition hover:border-sky-400/60 hover:bg-slate-800">
            <div className="flex gap-2">
              <div className="mt-0.5 text-sky-300"><AssetIcon category={asset.category} /></div>
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2"><span className="text-sm font-medium text-white">{asset.name}</span><span className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${threatStyles[asset.threat_level]}`}>{asset.threat_level}</span></div>
                <div className="mt-1 flex items-center gap-1 text-xs text-slate-400"><MapPin className="h-3 w-3" />{asset.district}</div>
                <div className="mt-2 text-xs text-slate-300">{asset.estimated_arrival_minutes == null ? "No projected arrival" : `ETA ${asset.estimated_arrival_minutes} min`}{asset.distance_to_storm_km != null && ` · ${asset.distance_to_storm_km} km`}</div>
              </div>
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
}
