import { cn } from "@/lib/utils";

export type RiskLevel = "low" | "moderate" | "high" | "severe";

const riskStyles: Record<RiskLevel, string> = {
  low: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  moderate: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  high: "bg-orange-500/25 text-orange-200 border-orange-500/40",
  severe: "bg-red-500/25 text-red-200 border-red-500/40",
};

interface BadgeProps {
  level: RiskLevel | string;
  className?: string;
  size?: "sm" | "md";
}

export function Badge({ level, className, size = "sm" }: BadgeProps) {
  const normalized = (level in riskStyles ? level : "moderate") as RiskLevel;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border font-semibold uppercase tracking-wider",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
        riskStyles[normalized],
        className
      )}
    >
      {normalized}
    </span>
  );
}
