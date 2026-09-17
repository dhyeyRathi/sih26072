import { StormCell, RiskAssessment } from "@/lib/types";
import { Zap, Wind, Navigation, Activity, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface StormDetailsProps {
  storm: StormCell | null;
  risk: RiskAssessment | null;
  onClose: () => void;
}

export function StormDetails({ storm, risk, onClose }: StormDetailsProps) {
  if (!storm) return null;

  const getIntensityColor = (intensity: string) => {
    switch (intensity) {
      case 'moderate': return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20';
      case 'strong': return 'text-orange-400 bg-orange-400/10 border-orange-400/20';
      case 'severe': return 'text-red-400 bg-red-400/10 border-red-400/20';
      default: return 'text-blue-400 bg-blue-400/10 border-blue-400/20';
    }
  };

  return (
    <div className="absolute top-6 right-6 w-80 bg-[#0a0e27]/90 backdrop-blur-xl border border-slate-700/50 rounded-xl shadow-2xl overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            Storm {storm.cell_id}
            {storm.trend === 'intensifying' && <span className="flex h-2 w-2 rounded-full bg-red-500 animate-pulse" title="Intensifying" />}
          </h2>
          <div className={cn("text-xs font-medium px-2 py-0.5 rounded-full mt-1 border inline-block uppercase tracking-wider", getIntensityColor(storm.intensity))}>
            {storm.intensity}
          </div>
        </div>
        <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-md transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-px bg-slate-700/50">
        <div className="bg-[#0a0e27]/90 p-4">
          <div className="flex items-center gap-2 text-slate-400 mb-1">
            <Activity className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wider">Reflectivity</span>
          </div>
          <div className="text-xl font-bold text-white">
            {storm.max_reflectivity_dbz.toFixed(1)} <span className="text-sm font-normal text-slate-400">dBZ</span>
          </div>
        </div>

        <div className="bg-[#0a0e27]/90 p-4">
          <div className="flex items-center gap-2 text-slate-400 mb-1">
            <Navigation className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wider">Direction</span>
          </div>
          <div className="text-xl font-bold text-white flex items-center gap-2">
            {storm.movement_direction_deg.toFixed(0)}°
            <Wind className="w-4 h-4" style={{ transform: `rotate(${storm.movement_direction_deg}deg)` }} />
          </div>
        </div>

        <div className="bg-[#0a0e27]/90 p-4">
          <div className="flex items-center gap-2 text-slate-400 mb-1">
            <Wind className="w-4 h-4" />
            <span className="text-xs uppercase tracking-wider">Speed</span>
          </div>
          <div className="text-xl font-bold text-white">
            {storm.movement_speed_kmh.toFixed(1)} <span className="text-sm font-normal text-slate-400">km/h</span>
          </div>
        </div>

        <div className="bg-[#0a0e27]/90 p-4">
          <div className="flex items-center gap-2 text-slate-400 mb-1">
            <Zap className="w-4 h-4 text-amber-400" />
            <span className="text-xs uppercase tracking-wider">Lightning</span>
          </div>
          <div className="text-xl font-bold text-white">
            {storm.lightning_rate.toFixed(1)} <span className="text-sm font-normal text-slate-400">/min</span>
          </div>
        </div>
      </div>

      {/* Risk Section */}
      {risk && (
        <div className="p-4 bg-slate-800/30">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Model Probabilities</h3>
          
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-300">Thunderstorm</span>
                <span className="font-mono text-white">{(risk.thunderstorm_probability * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 w-full bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className={cn("h-full rounded-full", risk.thunderstorm_probability > 0.6 ? "bg-red-500" : "bg-blue-500")}
                  style={{ width: `${risk.thunderstorm_probability * 100}%` }}
                />
              </div>
            </div>
            
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-300">Lightning</span>
                <span className="font-mono text-white">{(risk.lightning_probability * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 w-full bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className={cn("h-full rounded-full", risk.lightning_probability > 0.6 ? "bg-amber-500" : "bg-blue-500")}
                  style={{ width: `${risk.lightning_probability * 100}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
