import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface MetricTileProps {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  unit?: string;
  className?: string;
}

export function MetricTile({ icon, label, value, unit, className }: MetricTileProps) {
  return (
    <div className={cn("bg-[var(--surface)]/90 p-4", className)}>
      <div className="mb-1 flex items-center gap-2 text-slate-400">
        {icon}
        <span className="text-xs uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-xl font-bold text-white">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-slate-400">{unit}</span>}
      </div>
    </div>
  );
}
