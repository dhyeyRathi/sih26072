"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Building2, MapPin, Plane, Route, X } from "lucide-react";
import { Panel } from "@/components/ui/Panel";

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
    <Panel
      variant="opaque"
      className="absolute right-4 top-4 z-40 w-[calc(100vw-2rem)] md:w-[24rem] max-h-[calc(100vh-6rem)] shadow-2xl"
      header={
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-base font-bold text-white tracking-wide">
              <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 drop-shadow-[0_0_8px_rgba(251,191,36,0.5)]" />
              <span className="truncate">Exposure & Assets</span>
            </div>
            <p className="mt-1 text-xs font-medium text-slate-400 leading-relaxed">
              Forecast-path impact on critical Gujarat infrastructure.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close exposure panel"
            className="shrink-0 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      }
    >
      {data?.summary && (
        <div className="grid grid-cols-3 gap-px border-b border-white/10 bg-white/10 text-center shrink-0">
          <div className="bg-slate-900/90 p-3">
            <div className="text-lg font-extrabold text-rose-400 drop-shadow-sm">{data.summary.critical_count ?? 0}</div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mt-0.5">Critical</div>
          </div>
          <div className="bg-slate-900/90 p-3">
            <div className="text-lg font-extrabold text-orange-400 drop-shadow-sm">{data.summary.warning_count ?? 0}</div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mt-0.5">Warning</div>
          </div>
          <div className="bg-slate-900/90 p-3">
            <div className="text-lg font-extrabold text-amber-300 drop-shadow-sm">{data.summary.composite_exposure_score ?? 0}</div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mt-0.5">Score</div>
          </div>
        </div>
      )}

      <div className="flex-1 min-h-0 space-y-3 overflow-y-auto p-4 no-scrollbar">
        {error && <p className="rounded-xl border border-rose-400/30 bg-rose-500/10 p-4 text-sm font-medium text-rose-200 shadow-sm">{error}</p>}
        {!error && assets.length === 0 && <p className="p-4 text-sm font-medium text-slate-400">Loading critical infrastructure…</p>}
        {(threatened.length ? threatened : assets).map((asset) => (
          <button key={asset.id} onClick={() => onFocus({ lat: asset.lat, lon: asset.lon })} className="group w-full rounded-xl border border-white/10 bg-[#0f1629] p-4 text-left shadow-md transition-all duration-300 hover:-translate-y-0.5 hover:border-white/20 hover:bg-[#151d36] hover:shadow-lg">
            <div className="flex gap-3">
              <div className="mt-0.5 rounded-full bg-black/40 p-2 border border-white/10 text-sky-400 shadow-inner"><AssetIcon category={asset.category} /></div>
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2"><span className="text-sm font-bold text-white tracking-wide">{asset.name}</span><span className={`shrink-0 rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${threatStyles[asset.threat_level]}`}>{asset.threat_level}</span></div>
                <div className="mt-1.5 flex items-center gap-1.5 text-xs font-medium text-slate-400"><MapPin className="h-3.5 w-3.5" />{asset.district}</div>
                <div className="mt-3 text-xs font-semibold text-slate-300 bg-white/5 rounded-lg p-2 border border-white/5 inline-block">
                  {asset.estimated_arrival_minutes == null ? "No projected arrival" : `ETA ${asset.estimated_arrival_minutes} min`}
                  {asset.distance_to_storm_km != null && <span className="text-slate-500 font-normal"> · {asset.distance_to_storm_km} km</span>}
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>
    </Panel>
  );
}
