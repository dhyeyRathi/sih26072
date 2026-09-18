import { RiskAssessment } from "@/lib/types";
import { AlertTriangle, BrainCircuit, Clock, MapPin, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

interface RiskPanelProps {
  risks: RiskAssessment[];
  onSelect?: (cellId: string) => void;
  onExplain?: (cellId: string) => void;
}

export function RiskPanel({ risks, onSelect, onExplain }: RiskPanelProps) {
  // Sort risks by severity
  const sortedRisks = [...risks].sort((a, b) => {
    const levels = { severe: 4, high: 3, moderate: 2, low: 1 };
    return levels[b.risk_level] - levels[a.risk_level];
  });

  const highRisks = sortedRisks.filter(r => ['severe', 'high'].includes(r.risk_level));

  if (highRisks.length === 0) return null;

  return (
    <div className="absolute top-4 left-4 w-80 bg-[#0a0e27]/90 backdrop-blur-xl border border-slate-700/50 rounded-xl shadow-2xl overflow-hidden flex flex-col z-30">
      <div className="bg-red-500/10 border-b border-red-500/20 p-4">
        <div className="flex items-center gap-2 text-red-400 font-bold">
          <ShieldAlert className="w-5 h-5" />
          High Risk Threats ({highRisks.length})
        </div>
      </div>

      <div className="max-h-96 overflow-y-auto p-4 space-y-3">
        {highRisks.map((risk) => (
          <div 
            key={risk.cell_id} 
            onClick={() => onSelect?.(risk.cell_id)}
            className="bg-slate-800/60 rounded-lg p-3 border border-slate-700/60 cursor-pointer hover:bg-slate-700/60 hover:border-slate-500/60 transition-all shadow-md"
          >
            <div className="flex justify-between items-start mb-2">
              <div className="font-semibold text-white">Storm {risk.cell_id}</div>
              <div className={cn(
                "text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider",
                risk.risk_level === 'severe' ? "bg-red-500 text-white" : "bg-orange-500 text-white"
              )}>
                {risk.risk_level}
              </div>
            </div>

            <div className="space-y-2 text-sm text-slate-300">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-slate-400" />
                <span>Probabilities: TS {(risk.thunderstorm_probability * 100).toFixed(0)}% / LT {(risk.lightning_probability * 100).toFixed(0)}%</span>
              </div>
              
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-slate-400" />
                <span>Moving {risk.direction_deg.toFixed(0)}° at {risk.speed_kmh.toFixed(0)} km/h</span>
              </div>
              
              {risk.eta_minutes !== undefined && (
                <div className="flex items-center gap-2 text-amber-400">
                  <Clock className="w-4 h-4" />
                  <span className="font-medium">ETA: {risk.eta_minutes} min to target</span>
                </div>
              )}
              <button onClick={(event) => { event.stopPropagation(); onExplain?.(risk.cell_id); }} className="mt-1 flex items-center gap-1 text-xs font-medium text-sky-300 hover:text-sky-100"><BrainCircuit className="h-3.5 w-3.5" /> Explain warning</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
