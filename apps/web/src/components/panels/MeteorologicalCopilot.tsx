"use client";

import { FormEvent, useEffect, useState } from "react";
import { Bot, Send, Sparkles, X } from "lucide-react";

type Suggestion = { id: string; label: string; question: string };
type Citation = { title?: string; source_title?: string; url?: string; document_id?: string; excerpt?: string };
type CopilotResult = { answer: string; sources?: Citation[]; tool_calls?: Array<{ name: string; available: boolean; purpose: string }>; guardrails?: string[] };

interface MeteorologicalCopilotProps { open: boolean; cellId: string | null; onClose: () => void; }

export function MeteorologicalCopilot({ open, cellId, onClose }: MeteorologicalCopilotProps) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<CopilotResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    fetch("/api/copilot/suggestions")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Copilot suggestions are unavailable")))
      .then((body) => setSuggestions(body.suggestions ?? []))
      .catch((reason: Error) => setError(reason.message));
  }, [open]);

  const submit = async (event?: FormEvent, suggestedQuestion?: string) => {
    event?.preventDefault();
    const prompt = (suggestedQuestion ?? question).trim();
    if (!prompt || loading) return;
    setQuestion(prompt);
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/copilot/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: prompt, cell_id: cellId, include_live_data: true }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Copilot request failed");
      setResult(body);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Copilot request failed"); }
    finally { setLoading(false); }
  };

  if (!open) return null;
  return <aside className="absolute bottom-6 right-4 z-40 flex h-[34rem] w-[25rem] flex-col overflow-hidden rounded-2xl border border-sky-400/25 bg-[#0a0e27]/95 shadow-2xl backdrop-blur-xl"><header className="flex items-start justify-between border-b border-slate-700/70 p-4"><div><h2 className="flex items-center gap-2 font-bold text-white"><Bot className="h-5 w-5 text-sky-300" /> Meteorological copilot</h2><p className="mt-1 text-xs text-slate-400">Source-grounded guidance and inspectable live tools.</p></div><button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"><X className="h-5 w-5" /></button></header><div className="min-h-0 flex-1 overflow-y-auto p-4"><div className="mb-3 flex flex-wrap gap-1.5">{suggestions.slice(0, 4).map((suggestion) => <button key={suggestion.id} onClick={() => void submit(undefined, suggestion.question)} className="rounded-full border border-sky-400/20 bg-sky-400/5 px-2 py-1 text-[11px] text-sky-100 hover:bg-sky-400/15">{suggestion.label}</button>)}</div>{loading && <p className="flex items-center gap-2 text-sm text-sky-200"><Sparkles className="h-4 w-4 animate-pulse" /> Grounding response in platform data…</p>}{error && <p className="rounded border border-rose-400/30 bg-rose-500/10 p-2 text-sm text-rose-200">{error}</p>}{result && <article><p className="whitespace-pre-wrap text-sm leading-6 text-slate-200">{result.answer}</p>{result.tool_calls && result.tool_calls.length > 0 && <div className="mt-3 flex flex-wrap gap-1">{result.tool_calls.map((tool) => <span key={tool.name} className="rounded bg-slate-800 px-1.5 py-1 text-[10px] text-slate-300">{tool.available ? "●" : "○"} {tool.name.replaceAll("_", " ")}</span>)}</div>}{result.sources && result.sources.length > 0 && <div className="mt-4 border-t border-slate-700 pt-3"><h3 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Sources</h3>{result.sources.map((source, index) => <div key={source.document_id ?? index} className="mt-1 text-xs text-slate-400">{source.url ? <a className="text-sky-300 underline hover:text-sky-200" href={source.url} target="_blank" rel="noreferrer">{source.title ?? source.source_title ?? "Guidance source"}</a> : <span>{source.title ?? source.source_title ?? "Guidance source"}</span>}{source.excerpt && <span> — {source.excerpt}</span>}</div>)}</div>}</article>}</div><form onSubmit={(event) => void submit(event)} className="flex gap-2 border-t border-slate-700/70 p-3"><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={cellId ? `Ask about ${cellId}…` : "Ask about active weather…"} className="min-w-0 flex-1 rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500 focus:border-sky-400" /><button disabled={loading || !question.trim()} className="rounded-lg bg-sky-600 px-3 text-white hover:bg-sky-500 disabled:opacity-50" aria-label="Ask copilot"><Send className="h-4 w-4" /></button></form></aside>;
}
