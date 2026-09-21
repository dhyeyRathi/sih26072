"use client";

import { SystemHealth, StormUpdatePayload, RiskAssessment } from "@/lib/types";
import { format, formatDistanceToNowStrict } from "date-fns";
import { cn } from "@/lib/utils";
import {
  Wifi, WifiOff, BarChart3, Building2, ShieldCheck,
  CloudLightning, Activity,
} from "lucide-react";
import { ReactNode } from "react";
import * as Tooltip from "@radix-ui/react-tooltip";

interface StatusBarProps {
  health: SystemHealth | null;
  isConnected: boolean;
  lastMessageTime: Date | null;
  pendingAlertCount?: number;
  stormData?: StormUpdatePayload | null;
  onOpenExposure?: () => void;
  onOpenDesk?: () => void;
  onOpenAblation?: () => void;
}

const RISK_ORDER = { low: 0, moderate: 1, high: 2, severe: 3 };

function highestRisk(risks: StormUpdatePayload["risks"]): RiskAssessment["risk_level"] {
  if (!risks.length) return "low";
  return risks.reduce<RiskAssessment["risk_level"]>((max, r) =>
    RISK_ORDER[r.risk_level] > RISK_ORDER[max] ? r.risk_level : max
  , "low");
}

function ToolButton({
  label, title, onClick, icon, badge,
}: {
  label: string;
  title: string;
  onClick?: () => void;
  icon: ReactNode;
  badge?: number;
}) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          onClick={onClick}
          title={title}
          className="relative flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-semibold tracking-wide text-slate-400 transition-all duration-200 hover:bg-white/10 hover:text-white hover:shadow-sm active:scale-95"
        >
          {icon}
          <span className="hidden lg:inline">{label}</span>
          {badge != null && badge > 0 && (
            <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white">
              {badge}
            </span>
          )}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="bottom"
          className="rounded-md bg-slate-900/95 backdrop-blur px-2.5 py-1.5 text-xs text-slate-200 shadow-xl border border-white/10 z-50 font-medium"
        >
          {title}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

export function StatusBar({
  health, isConnected, lastMessageTime, pendingAlertCount = 0,
  stormData, onOpenExposure, onOpenDesk, onOpenAblation,
}: StatusBarProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case "live": return "bg-emerald-500";
      case "delayed": return "bg-amber-500";
      case "stale": return "bg-rose-500";
      default: return "bg-slate-500";
    }
  };

  const activeCells = stormData?.storms.length ?? 0;
  const maxRisk = stormData ? highestRisk(stormData.risks) : null;
  const exposureScore = stormData?.exposure_summary?.composite_exposure_score;

  return (
    <Tooltip.Provider delayDuration={300}>
      <header className="flex items-center justify-between gap-4 border-b border-white/5 bg-[var(--surface)]/90 backdrop-blur-xl px-4 py-2 text-sm text-slate-300 shadow-sm relative z-50">
        <div className="flex min-w-0 flex-1 items-center gap-4">
          <div className="flex items-center gap-2 shrink-0">
            {isConnected ? (
              <Wifi className="h-4 w-4 text-emerald-400" />
            ) : (
              <WifiOff className="h-4 w-4 text-rose-400" />
            )}
            <div>
              <div className="font-semibold text-white tracking-tight leading-tight">SIH26072 Nowcast</div>
              <div className="text-[10px] font-medium text-slate-400">Gujarat / Ahmedabad MVP</div>
            </div>
          </div>

          {health && (
            <div 
              className="hidden md:flex min-w-0 items-center gap-3 border-l border-white/10 pl-4 overflow-hidden"
              style={{ maskImage: 'linear-gradient(to right, black 85%, transparent 100%)', WebkitMaskImage: 'linear-gradient(to right, black 85%, transparent 100%)' }}
            >
              {Object.entries(health.sources).map(([name, source]) => (
                <Tooltip.Root key={name}>
                  <Tooltip.Trigger asChild>
                    <div className="flex shrink-0 cursor-default items-center gap-1.5 transition-opacity hover:opacity-80">
                      <div className={cn("h-2 w-2 rounded-full shadow-[0_0_8px_rgba(0,0,0,0.5)]", getStatusColor(source.status))} />
                      <span className="capitalize text-[11px] font-medium tracking-wide">{name}</span>
                    </div>
                  </Tooltip.Trigger>
                  <Tooltip.Portal>
                    <Tooltip.Content className="rounded-md bg-slate-900/95 backdrop-blur px-2.5 py-1.5 text-xs border border-white/10 shadow-xl z-50">
                      <span className="font-medium text-white capitalize">{source.status}</span> · {source.latency_ms ?? "—"}ms
                    </Tooltip.Content>
                  </Tooltip.Portal>
                </Tooltip.Root>
              ))}
            </div>
          )}
        </div>

        {stormData && (
          <div className="hidden xl:flex shrink-0 items-center gap-4 rounded-full border border-white/5 bg-white/5 px-4 py-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
            <div className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide">
              <CloudLightning className="h-3.5 w-3.5 text-sky-400 drop-shadow-[0_0_8px_rgba(56,189,248,0.5)]" />
              <span className="text-slate-400">Cells</span>
              <span className="font-mono text-sm font-bold text-white">{activeCells}</span>
            </div>
            {maxRisk && (
              <div className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide border-l border-white/10 pl-4">
                <Activity className="h-3.5 w-3.5 text-amber-400" />
                <span className="text-slate-400">Peak risk</span>
                <span className={cn(
                  "font-bold uppercase tracking-wider drop-shadow-sm",
                  maxRisk === "severe" ? "text-red-400" :
                  maxRisk === "high" ? "text-orange-400" :
                  maxRisk === "moderate" ? "text-amber-400" : "text-emerald-400"
                )}>{maxRisk}</span>
              </div>
            )}
            {exposureScore != null && (
              <div className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide border-l border-white/10 pl-4">
                <span className="text-slate-400">Exposure</span>
                <span className="font-mono text-sm font-bold text-white">{exposureScore}</span>
              </div>
            )}
            {lastMessageTime && (
              <div className="text-[10px] text-slate-500 border-l border-white/10 pl-4 font-medium">
                Updated {formatDistanceToNowStrict(lastMessageTime, { addSuffix: true })}
              </div>
            )}
          </div>
        )}

        <div className="flex items-center gap-2 shrink-0">
          <nav className="flex items-center gap-1 bg-white/5 rounded-lg p-1 border border-white/5" aria-label="Operations tools">
            <ToolButton label="Desk" title="Forecaster warning desk" onClick={onOpenDesk} icon={<ShieldCheck className="h-4 w-4" />} badge={pendingAlertCount} />
            <ToolButton label="Models" title="Model ablation comparison" onClick={onOpenAblation} icon={<BarChart3 className="h-4 w-4" />} />
          </nav>

          {health && (
            <div className="ml-2 hidden sm:flex items-center gap-2 border-l border-white/10 pl-4 text-[11px] font-medium tracking-wide">
              <span className="text-slate-400">Model</span>
              <span className={cn(
                "capitalize font-bold drop-shadow-sm",
                health.model.status === "ready" ? "text-emerald-400" : "text-amber-400"
              )}>
                {health.model.status}
              </span>
            </div>
          )}

          <div className="ml-1 font-mono text-xs font-semibold text-slate-300 border-l border-white/10 pl-3">
            {lastMessageTime ? format(lastMessageTime, "HH:mm:ss") : "--:--:--"}
          </div>
        </div>
      </header>
    </Tooltip.Provider>
  );
}
