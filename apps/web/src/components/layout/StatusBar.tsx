import { SystemHealth } from "@/lib/types";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import { Wifi, WifiOff, BarChart3, Bot, Building2, History, ShieldCheck } from "lucide-react";

interface StatusBarProps {
  health: SystemHealth | null;
  isConnected: boolean;
  lastMessageTime: Date | null;
  pendingAlertCount?: number;
  onOpenExposure?: () => void;
  onOpenDesk?: () => void;
  onOpenHistorical?: () => void;
  onOpenAblation?: () => void;
  onOpenCopilot?: () => void;
}

export function StatusBar({ health, isConnected, lastMessageTime, pendingAlertCount = 0, onOpenExposure, onOpenDesk, onOpenHistorical, onOpenAblation, onOpenCopilot }: StatusBarProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'live': return 'bg-emerald-500';
      case 'delayed': return 'bg-amber-500';
      case 'stale': return 'bg-rose-500';
      default: return 'bg-slate-500';
    }
  };

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-[#0a0e27] border-b border-slate-800 text-sm text-slate-300">
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2">
          {isConnected ? (
            <Wifi className="w-4 h-4 text-emerald-500" />
          ) : (
            <WifiOff className="w-4 h-4 text-rose-500" />
          )}
          <span className="font-semibold text-white">SIH26072 Nowcast</span>
        </div>

        {health && (
          <div className="flex items-center space-x-4">
            {Object.entries(health.sources).map(([name, source]) => (
              <div key={name} className="flex items-center space-x-1.5" title={source.last_data_at || 'Offline'}>
                <div className={cn("w-2 h-2 rounded-full", getStatusColor(source.status))} />
                <span className="capitalize">{name}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center space-x-3">
        <nav className="hidden items-center gap-1 xl:flex" aria-label="Operations tools">
          <button onClick={onOpenExposure} title="Exposure and assets" className="rounded p-1.5 text-slate-400 hover:bg-slate-800 hover:text-sky-200"><Building2 className="h-4 w-4" /></button>
          <button onClick={onOpenDesk} title="Forecaster warning desk" className="relative rounded p-1.5 text-slate-400 hover:bg-slate-800 hover:text-emerald-200"><ShieldCheck className="h-4 w-4" />{pendingAlertCount > 0 && <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white">{pendingAlertCount}</span>}</button>
          <button onClick={onOpenHistorical} title="Historical analogues" className="rounded p-1.5 text-slate-400 hover:bg-slate-800 hover:text-violet-200"><History className="h-4 w-4" /></button>
          <button onClick={onOpenAblation} title="Model ablation" className="rounded p-1.5 text-slate-400 hover:bg-slate-800 hover:text-violet-200"><BarChart3 className="h-4 w-4" /></button>
          <button onClick={onOpenCopilot} title="Meteorological copilot" className="rounded p-1.5 text-slate-400 hover:bg-slate-800 hover:text-sky-200"><Bot className="h-4 w-4" /></button>
        </nav>
        {health && (
          <div className="flex items-center space-x-2 border-l border-slate-700 pl-4">
            <span className="text-slate-400">Model:</span>
            <span className={cn(
              "capitalize",
              health.model.status === 'ready' ? "text-emerald-400" : "text-amber-400"
            )}>
              {health.model.status}
            </span>
          </div>
        )}
        <div className="font-mono text-slate-400 border-l border-slate-700 pl-4">
          {lastMessageTime ? format(lastMessageTime, "HH:mm:ss") : "--:--:--"}
        </div>
      </div>
    </div>
  );
}
