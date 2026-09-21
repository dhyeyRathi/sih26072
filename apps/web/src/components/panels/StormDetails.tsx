import { StormCell, RiskAssessment } from "@/lib/types";
import { Zap, Wind, Navigation, Activity, BrainCircuit, X, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { Panel } from "@/components/ui/Panel";
import { Badge } from "@/components/ui/Badge";
import { MetricTile } from "@/components/ui/MetricTile";
import { getNearestCity } from "@/lib/geocoding";

interface StormDetailsProps {
  storm: StormCell | null;
  risk: RiskAssessment | null;
  onClose: () => void;
  onExplain?: (cellId: string) => void;
  awaitingSelection?: boolean;
}

function trendLabel(trend: string) {
  if (trend === "intensifying") return { icon: TrendingUp, text: "Intensifying", color: "text-red-400" };
  if (trend === "weakening" || trend === "dissipating") return { icon: TrendingDown, text: trend, color: "text-emerald-400" };
  return { icon: Minus, text: "Steady", color: "text-slate-400" };
}

export function StormDetails({ storm, risk, onClose, onExplain, awaitingSelection }: StormDetailsProps) {
  if (!storm) {
    if (!awaitingSelection) return null;
    return (
      <Panel className="absolute top-4 right-4 z-30 w-80">
        <div className="p-4">
          <h2 className="text-sm font-semibold text-white">Storm details</h2>
          <p className="mt-2 text-sm text-slate-400">Awaiting cell data. Select a storm on the map when live nowcast arrives.</p>
        </div>
      </Panel>
    );
  }

  const trend = trendLabel(storm.trend);
  const TrendIcon = trend.icon;

  const startCity = getNearestCity(storm.center_lat, storm.center_lon);
  
  // Extrapolate 1 hour (or 60 mins) to find the destination
  const distKm = storm.movement_speed_kmh;
  const dirRad = storm.movement_direction_deg * (Math.PI / 180);
  const dLat = (distKm * Math.cos(dirRad)) / 111.0;
  const dLon = (distKm * Math.sin(dirRad)) / (111.0 * Math.cos(storm.center_lat * (Math.PI / 180)));
  const endLat = storm.center_lat + dLat;
  const endLon = storm.center_lon + dLon;
  const endCity = getNearestCity(endLat, endLon);

  return (
    <Panel
      className="absolute top-4 right-4 z-30 w-80 max-h-[85vh] flex flex-col overflow-hidden"
      header={
        <div className="flex flex-col gap-2">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h2 className="flex items-center gap-2 text-lg font-bold text-white">
              Storm {storm.cell_id}
              {storm.trend === "intensifying" && (
                <span className="flex h-2 w-2 animate-pulse rounded-full bg-red-500" title="Intensifying" />
              )}
            </h2>
            <div className="mt-1 flex items-center gap-2">
              <Badge level={storm.intensity === "weak" ? "low" : storm.intensity === "moderate" ? "moderate" : storm.intensity === "strong" ? "high" : "severe"} size="md" />
              <span className={cn("flex items-center gap-1 text-xs capitalize", trend.color)}>
                <TrendIcon className="h-3 w-3" /> {trend.text}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-800 hover:text-white">
            <X className="h-5 w-5" />
          </button>
          </div>
          <div className="flex items-center text-xs font-medium text-slate-300 mt-1 pb-1">
            <span className="text-white truncate" title={startCity}>{startCity}</span>
            <span className="mx-2 text-slate-500">→</span>
            <span className="text-sky-300 truncate" title={endCity}>{endCity}</span>
          </div>
        </div>
      }
      footer={
        <button
          onClick={() => onExplain?.(storm.cell_id)}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-sky-400/30 bg-sky-400/10 px-3 py-2 text-xs font-semibold text-sky-100 transition hover:bg-sky-400/20"
        >
          <BrainCircuit className="h-4 w-4" /> Explain warning
        </button>
      }
    >
      <div className="overflow-y-auto flex-1 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent pb-4">
        <div className="grid grid-cols-2 gap-px bg-white/10">
        <MetricTile
          icon={<Activity className="h-4 w-4" />}
          label="Reflectivity"
          value={storm.max_reflectivity_dbz.toFixed(1)}
          unit="dBZ"
        />
        <MetricTile
          icon={
            <Navigation
              className="h-4 w-4 transition-transform"
              style={{ transform: `rotate(${storm.movement_direction_deg}deg)` }}
            />
          }
          label="Direction"
          value={`${storm.movement_direction_deg.toFixed(0)}°`}
        />
        <MetricTile
          icon={<Wind className="h-4 w-4" />}
          label="Speed"
          value={storm.movement_speed_kmh.toFixed(1)}
          unit="km/h"
        />
        <MetricTile
          icon={<Zap className="h-4 w-4 text-amber-400" />}
          label="Lightning"
          value={storm.lightning_rate.toFixed(1)}
          unit="/min"
        />
      </div>

      {/* Severe Convective Physical Indicators */}
      {(risk?.vil_kg_m2 != null || storm.vil_kg_m2 != null) && (
        <div className="border-t border-white/5 bg-slate-900/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-[11px] font-bold uppercase tracking-widest text-sky-400">Physics & Indicators</h3>
            {(risk?.lightning_jump?.jump_detected || storm.lightning_jump?.jump_detected) && (
              <span className="animate-pulse rounded-md bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500/40">
                2σ LIGHTNING JUMP
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg bg-black/40 p-2.5 border border-white/5">
              <div className="text-[10px] text-slate-400">VIL (Liquid Mass)</div>
              <div className="font-mono text-sm font-bold text-white mt-0.5">
                {(risk?.vil_kg_m2 ?? storm.vil_kg_m2 ?? 0).toFixed(1)} <span className="text-[10px] text-slate-400 font-normal">kg/m²</span>
              </div>
            </div>

            <div className="rounded-lg bg-black/40 p-2.5 border border-white/5">
              <div className="text-[10px] text-slate-400">VIL Density</div>
              <div className="font-mono text-sm font-bold text-white mt-0.5 flex items-center justify-between">
                <span>{(risk?.vil_density_g_m3 ?? storm.vil_density_g_m3 ?? 0).toFixed(2)} <span className="text-[10px] text-slate-400 font-normal">g/m³</span></span>
                {(risk?.vil_density_g_m3 ?? storm.vil_density_g_m3 ?? 0) >= 3.5 && (
                  <span className="text-[9px] font-bold text-red-400 bg-red-500/20 px-1.5 py-0.5 rounded">HAIL CORE</span>
                )}
              </div>
            </div>

            <div className="rounded-lg bg-black/40 p-2.5 border border-white/5">
              <div className="text-[10px] text-slate-400">Echo Top Height</div>
              <div className="font-mono text-sm font-bold text-white mt-0.5">
                {(risk?.echo_top_km ?? storm.echo_top_km ?? 0).toFixed(1)} <span className="text-[10px] text-slate-400 font-normal">km</span>
              </div>
            </div>

            <div className="rounded-lg bg-black/40 p-2.5 border border-white/5">
              <div className="text-[10px] text-slate-400">Max Updraft W_max</div>
              <div className="font-mono text-sm font-bold text-white mt-0.5">
                {(risk?.w_max_m_s ?? storm.w_max_m_s ?? 0).toFixed(1)} <span className="text-[10px] text-slate-400 font-normal">m/s</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {risk && (
        <div className="border-t border-white/5 bg-black/20 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Model Probabilities</h3>
            {risk.confidence_score != null && (
              <span className="rounded-md bg-white/10 px-2 py-0.5 text-[10px] font-mono font-medium text-slate-300 border border-white/5 shadow-sm">
                {Math.round(risk.confidence_score * 100)}% conf.
              </span>
            )}
          </div>
          {risk.raw_risk_level && (
            <div className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              Nowcaster MLP · operational risk
            </div>
          )}

          <div className="space-y-3">
            <div>
              <div className="mb-1 flex justify-between text-sm">
                <span className="text-slate-300">Thunderstorm</span>
                <span className="font-mono text-white">{(risk.thunderstorm_probability * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-700">
                <div
                  className={cn("h-full rounded-full", risk.thunderstorm_probability > 0.6 ? "bg-red-500" : "bg-sky-500")}
                  style={{ width: `${risk.thunderstorm_probability * 100}%` }}
                />
              </div>
            </div>

            <div>
              <div className="mb-1 flex justify-between text-sm">
                <span className="text-slate-300">Lightning Strike</span>
                <span className="font-mono text-white">{(risk.lightning_probability * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-700">
                <div
                  className={cn("h-full rounded-full", risk.lightning_probability > 0.6 ? "bg-amber-500" : "bg-sky-500")}
                  style={{ width: `${risk.lightning_probability * 100}%` }}
                />
              </div>
            </div>

            {risk.eta_minutes != null && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-200 mt-4 shadow-sm">
                Estimated arrival at Ahmedabad: <strong className="font-bold text-amber-400 text-sm ml-1">{risk.eta_minutes} min</strong>
              </div>
            )}

            {risk.risk_level && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Operational risk</span>
                <Badge level={risk.risk_level} size="md" />
              </div>
            )}
          </div>
        </div>
      )}
      </div>
    </Panel>
  );
}
