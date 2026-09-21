"use client";

import { useState } from "react";
import { RiskAssessment } from "@/lib/types";
import { BrainCircuit, Clock, MapPin, ShieldAlert, TrendingDown, TrendingUp, Minus, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Panel } from "@/components/ui/Panel";
import { Badge } from "@/components/ui/Badge";

interface RiskPanelProps {
  risks: RiskAssessment[];
  onSelect?: (cellId: string) => void;
  onExplain?: (cellId: string) => void;
}

type FilterMode = "all" | "watch" | "high";

const LEVEL_ORDER = { severe: 4, high: 3, moderate: 2, low: 1 };
const WATCH_LEVELS = new Set(["moderate", "high", "severe"]);

function TrendIcon({ trend }: { trend: RiskAssessment["trend"] }) {
  if (trend === "intensifying") return <TrendingUp className="h-3.5 w-3.5 text-red-400" />;
  if (trend === "weakening" || trend === "dissipating") return <TrendingDown className="h-3.5 w-3.5 text-emerald-400" />;
  return <Minus className="h-3.5 w-3.5 text-slate-500" />;
}

export function RiskPanel({ risks, onSelect, onExplain }: RiskPanelProps) {
  const [filter, setFilter] = useState<FilterMode>("watch");

  const sortedRisks = [...risks].sort((a, b) => {
    const levelDiff = LEVEL_ORDER[b.risk_level] - LEVEL_ORDER[a.risk_level];
    if (levelDiff !== 0) return levelDiff;
    const etaA = a.eta_minutes ?? 999;
    const etaB = b.eta_minutes ?? 999;
    return etaA - etaB;
  });

  const filtered = sortedRisks.filter((r) => {
    if (filter === "all") return true;
    if (filter === "watch") return WATCH_LEVELS.has(r.risk_level);
    return r.risk_level === "high" || r.risk_level === "severe";
  });

  const elevatedCount = sortedRisks.filter((r) => WATCH_LEVELS.has(r.risk_level)).length;

  return (
    <Panel
      variant="opaque"
      className="absolute top-4 left-4 z-30 w-80 max-h-[calc(100vh-6rem)] shadow-2xl"
      accent={elevatedCount > 0 ? "danger" : "success"}
      header={
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-base font-bold text-white tracking-wide">
              {elevatedCount > 0 ? (
                <ShieldAlert className="h-5 w-5 text-red-400 drop-shadow-[0_0_8px_rgba(248,113,113,0.5)]" />
              ) : (
                <CheckCircle2 className="h-5 w-5 text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)]" />
              )}
              <span>Active Threats</span>
              {elevatedCount > 0 && (
                <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-[10px] font-bold text-red-300 shadow-[inset_0_0_0_1px_rgba(248,113,113,0.3)]">
                  {elevatedCount}
                </span>
              )}
            </div>
            <span className="text-[11px] font-medium text-slate-400">
              {filtered.length} storm{filtered.length !== 1 ? "s" : ""}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-1 rounded-lg bg-black/40 p-1 border border-white/10 text-center">
            {(["all", "watch", "high"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setFilter(mode)}
                className={cn(
                  "rounded-md py-1 text-[10px] font-bold uppercase tracking-wider transition-all",
                  filter === mode
                    ? "bg-white/15 text-white shadow-sm border border-white/10"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                )}
              >
                {mode === "watch" ? "Watch+" : mode === "high" ? "High+" : "All"}
              </button>
            ))}
          </div>
        </div>
      }
    >
      <div className="flex-1 min-h-0 space-y-3 overflow-y-auto p-4 no-scrollbar">
        {filtered.length === 0 ? (
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-6 text-center text-sm font-medium text-emerald-300">
            No elevated threats in current filter
          </div>
        ) : (
          filtered.map((risk) => (
            <div
              key={risk.cell_id}
              onClick={() => onSelect?.(risk.cell_id)}
              className="group cursor-pointer rounded-xl border border-white/10 bg-[#0f1629] p-4 shadow-md transition-all duration-300 hover:-translate-y-0.5 hover:border-white/20 hover:bg-[#151d36] hover:shadow-lg"
            >
              <div className="mb-3 flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white tracking-wide">Storm {risk.cell_id}</span>
                  <div className="rounded-full bg-black/20 p-1 backdrop-blur-sm border border-white/5">
                    <TrendIcon trend={risk.trend} />
                  </div>
                </div>
                <Badge level={risk.risk_level} />
              </div>

              {risk.confidence_score != null && (
                <div className="mb-2 text-[10px] text-slate-400">
                  Confidence <span className="font-mono text-slate-200">{Math.round(risk.confidence_score * 100)}%</span>
                </div>
              )}

              <div className="space-y-2 text-sm text-slate-300">
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span>Thunderstorm</span>
                    <span className="font-mono">{(risk.thunderstorm_probability * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-1 w-full overflow-hidden rounded-full bg-slate-700">
                    <div
                      className={cn("h-full rounded-full", risk.thunderstorm_probability > 0.6 ? "bg-red-500" : "bg-sky-500")}
                      style={{ width: `${risk.thunderstorm_probability * 100}%` }}
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span>Lightning</span>
                    <span className="font-mono">{(risk.lightning_probability * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-1 w-full overflow-hidden rounded-full bg-slate-700">
                    <div
                      className="h-full rounded-full bg-amber-500"
                      style={{ width: `${risk.lightning_probability * 100}%` }}
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2 text-xs font-medium">
                  <MapPin className="h-3.5 w-3.5 text-slate-400" />
                  <span className="text-slate-300">{risk.direction_deg.toFixed(0)}° at {risk.speed_kmh.toFixed(0)} km/h</span>
                </div>

                {risk.eta_minutes != null && (
                  <div className="flex items-center gap-2 text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 p-2 rounded-lg mt-2">
                    <Clock className="h-3.5 w-3.5" />
                    <span className="font-semibold">ETA Ahmedabad: {risk.eta_minutes} min</span>
                  </div>
                )}

                <button
                  onClick={(e) => { e.stopPropagation(); onExplain?.(risk.cell_id); }}
                  className="mt-1 flex items-center gap-1 text-xs font-medium text-sky-300 hover:text-sky-100"
                >
                  <BrainCircuit className="h-3.5 w-3.5" /> Explain warning
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </Panel>
  );
}
