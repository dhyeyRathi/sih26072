import { SystemHealth } from "@/lib/types";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import { Activity, Wifi, WifiOff, Clock, AlertTriangle } from "lucide-react";

interface StatusBarProps {
  health: SystemHealth | null;
  isConnected: boolean;
  lastMessageTime: Date | null;
}

export function StatusBar({ health, isConnected, lastMessageTime }: StatusBarProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'live': return 'bg-emerald-500';
      case 'delayed': return 'bg-amber-500';
      case 'stale': return 'bg-rose-500';
      default: return 'bg-slate-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'live': return <Activity className="w-4 h-4 text-emerald-500" />;
      case 'delayed': return <Clock className="w-4 h-4 text-amber-500" />;
      case 'stale': return <AlertTriangle className="w-4 h-4 text-rose-500" />;
      default: return <WifiOff className="w-4 h-4 text-slate-500" />;
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

      <div className="flex items-center space-x-4">
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
