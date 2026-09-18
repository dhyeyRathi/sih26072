"use client";

import { useEffect, useState } from "react";
import { History, RefreshCw, X } from "lucide-react";

type HistoricalEvent = { id: string; name: string; date?: string; impact_summary?: string; observed_rainfall_mm?: number; };
type Match = { event_id?: string; name?: string; event_name?: string; similarity?: number; match_percentage?: number; impact_summary?: string; };

interface HistoricalAnalogueDrawerProps { open: boolean; cellId: string | null; onClose: () => void; }

export function HistoricalAnalogueDrawer({ open, cellId, onClose }: HistoricalAnalogueDrawerProps) {
  const [events, setEvents] = useState<HistoricalEvent[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [metrics, setMetrics] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const load = async () => {
      try {
        const [eventsRes, metricsRes, matchRes] = await Promise.all([
          fetch("/api/historical/events"), fetch("/api/historical/metrics"), cellId ? fetch("/api/historical/match", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cell_id: cellId }) }) : Promise.resolve(null),
        ]);
        if (!eventsRes.ok || !metricsRes.ok || (matchRes && !matchRes.ok)) throw new Error("Historical intelligence is unavailable");
        const eventBody = await eventsRes.json();
        const metricBody = await metricsRes.json();
        const matchBody = matchRes ? await matchRes.json() : { matches: [] };
        if (!cancelled) { setEvents(eventBody.events ?? []); setMetrics(metricBody.metrics ?? metricBody); setMatches(matchBody.matches ?? []); }
      } catch (reason) { if (!cancelled) setError(reason instanceof Error ? reason.message : "Historical intelligence is unavailable"); }
    };
    void load();
    return () => { cancelled = true; };
  }, [cellId, open]);

  if (!open) return null;
  return <aside className="absolute bottom-24 right-4 z-40 flex max-h-[65vh] w-[25rem] flex-col overflow-hidden rounded-xl border border-slate-700/70 bg-[#0a0e27]/95 shadow-2xl backdrop-blur-xl"><header className="flex items-start justify-between border-b border-slate-700/60 p-4"><div><h2 className="flex items-center gap-2 font-bold text-white"><History className="h-5 w-5 text-violet-300" /> Historical analogues</h2><p className="mt-1 text-xs text-slate-400">Comparable Western India severe-weather events.</p></div><button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"><X className="h-5 w-5" /></button></header><div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">{error && <p className="text-sm text-rose-200">{error}</p>}{metrics && <div className="grid grid-cols-3 gap-2 rounded-lg bg-slate-900/70 p-3 text-center">{Object.entries(metrics).slice(0, 3).map(([name, value]) => <div key={name}><div className="font-mono text-sm text-violet-200">{typeof value === "number" ? `${(value * 100).toFixed(0)}%` : String(value)}</div><div className="text-[10px] uppercase text-slate-500">{name}</div></div>)}</div>}{matches.length > 0 && <section><h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">Current cell {cellId} matches</h3>{matches.map((match, index) => <div key={match.event_id ?? index} className="mb-2 rounded-lg border border-violet-400/20 bg-violet-400/5 p-3"><div className="flex justify-between gap-3 text-sm font-medium text-white"><span>{match.name ?? match.event_name}</span><span className="text-violet-200">{Math.round((match.similarity ?? match.match_percentage ?? 0) * ((match.similarity ?? 0) <= 1 ? 100 : 1))}%</span></div><p className="mt-1 text-xs text-slate-400">{match.impact_summary}</p></div>)}</section>}<section><h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">Archive</h3>{events.map((event) => <div key={event.id} className="mb-2 rounded-lg border border-slate-700 bg-slate-900/50 p-3"><div className="text-sm font-medium text-white">{event.name}</div><div className="mt-1 text-xs text-slate-400">{event.date} · {event.impact_summary}</div></div>)}</section><button className="flex w-full items-center justify-center gap-2 rounded border border-slate-600 py-2 text-xs text-slate-300 hover:bg-slate-800"><RefreshCw className="h-3.5 w-3.5" /> Replay available from event detail API</button></div></aside>;
}
