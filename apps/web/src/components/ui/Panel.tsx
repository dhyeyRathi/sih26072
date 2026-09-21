import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface PanelProps {
  children: ReactNode;
  className?: string;
  header?: ReactNode;
  footer?: ReactNode;
  accent?: "default" | "danger" | "success";
  variant?: "glass" | "opaque";
}

const accentStyles = {
  default: "border-b border-white/10 bg-white/5",
  danger: "border-b border-red-500/20 bg-gradient-to-r from-red-500/10 to-transparent",
  success: "border-b border-emerald-500/20 bg-gradient-to-r from-emerald-500/10 to-transparent",
};

export function Panel({ children, className, header, footer, accent = "default", variant = "glass" }: PanelProps) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.98 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={cn(
        variant === "opaque" ? "opaque-panel" : "glass-panel",
        "flex flex-col overflow-hidden rounded-2xl shadow-2xl ring-1 ring-white/5",
        className
      )}
    >
      {header && <div className={cn("px-5 py-4 backdrop-blur-sm shrink-0", accentStyles[accent])}>{header}</div>}
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">{children}</div>
      {footer && <div className="border-t border-white/10 bg-black/20 p-4 backdrop-blur-sm shrink-0">{footer}</div>}
    </motion.div>
  );
}
