"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, FileCode2, Radio, ShieldCheck, X, XCircle } from "lucide-react";
import { Panel } from "@/components/ui/Panel";

type AlertItem = {
  id: string;
  title: string;
  description?: string;
  risk_level: string;
  status: string;
  storm_cell_ids?: string[];
  valid_to?: string;
  evidence?: Record<string, unknown>;
};

interface ForecasterDeskProps {
  open: boolean;
  onClose: () => void;
  onPendingCountChange?: (count: number) => void;
}

export function ForecasterDesk({ open, onClose, onPendingCountChange }: ForecasterDeskProps) {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [approvedAlerts, setApprovedAlerts] = useState<AlertItem[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editedDescription, setEditedDescription] = useState("");

  const load = useCallback(async () => {
    try {
      const [pendingResponse, approvedResponse] = await Promise.all([
        fetch("/api/alerts/pending"),
        fetch("/api/alerts?status=approved"),
      ]);
      if (!pendingResponse.ok || !approvedResponse.ok) throw new Error("Unable to load the warning queue");
      const pendingBody = await pendingResponse.json();
      const approvedBody = await approvedResponse.json();
      const pending = pendingBody.alerts ?? [];
      setAlerts(pending);
      setApprovedAlerts(approvedBody.alerts ?? []);
      onPendingCountChange?.(pending.length);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to load the warning queue");
    }
  }, [onPendingCountChange]);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load, open]);

  const review = async (alertId: string, action: "approved" | "dismissed") => {
    setBusyId(alertId);
    setStatus(null);
    try {
      const response = await fetch(`/api/alerts/${alertId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          comment: `Forecaster ${action} warning.`,
          reviewer_name: "Duty forecaster",
          reviewer_designation: "Nowcasting forecaster",
          digital_sign_off: action === "approved",
        }),
      });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Review failed");
      await load();
      setStatus(action === "approved" ? "Warning approved and signed off." : "Warning dismissed.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Review failed");
    } finally { setBusyId(null); }
  };

  const modify = async (alertId: string) => {
    if (!editedDescription.trim()) return;
    setBusyId(alertId);
    setStatus(null);
    try {
      const response = await fetch(`/api/alerts/${alertId}/modify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ description: editedDescription.trim() }) });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Modification failed");
      setEditingId(null);
      setEditedDescription("");
      await load();
      setStatus("Warning recommendation updated and retained for review.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Modification failed");
    } finally { setBusyId(null); }
  };

  const broadcast = async (alertId: string) => {
    setBusyId(alertId);
    setStatus(null);
    try {
      const response = await fetch(`/api/alerts/${alertId}/broadcast`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Broadcast failed");
      const body = await response.json();
      setStatus(`Broadcast dispatched: ${body.broadcast?.total_recipients ?? 0} recipients.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Broadcast failed");
    } finally { setBusyId(null); }
  };

  if (!open) return null;
  return (
    <Panel variant="opaque" className="absolute right-4 md:right-[21.5rem] top-4 z-40 flex max-h-[calc(100vh-6rem)] w-[calc(100vw-2rem)] md:w-[26rem] shadow-2xl">
      <header className="flex items-start justify-between border-b border-[var(--border)] p-4">
        <div>
          <h2 className="flex items-center gap-2 font-bold text-white">
            <ShieldCheck className="h-5 w-5 text-emerald-300" /> Forecaster warning desk
          </h2>
          <p className="mt-1 text-xs text-slate-400">Human review remains required before dissemination.</p>
        </div>
        <button onClick={onClose} className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-800 hover:text-white">
          <X className="h-5 w-5" />
        </button>
      </header>
      {status && <p className="mx-3 mt-3 rounded border border-sky-400/20 bg-sky-400/10 p-2 text-xs text-sky-100">{status}</p>}
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {!status && alerts.length === 0 && <p className="p-3 text-sm text-slate-400">No pending warning recommendations.</p>}
        {alerts.map((alert) => <article key={alert.id} className="rounded-lg border border-slate-700 bg-slate-900/60 p-3"><div className="flex justify-between gap-2"><h3 className="text-sm font-semibold text-white">{alert.title}</h3><span className="h-fit rounded bg-rose-500/20 px-1.5 py-0.5 text-[10px] font-bold uppercase text-rose-200">{alert.risk_level}</span></div><p className="mt-2 text-xs leading-5 text-slate-300">{alert.description}</p><p className="mt-2 text-[11px] text-slate-500">Cells: {alert.storm_cell_ids?.join(", ") || "—"}</p>{editingId === alert.id && <div className="mt-3"><textarea value={editedDescription} onChange={(event) => setEditedDescription(event.target.value)} className="min-h-16 w-full rounded border border-slate-600 bg-slate-950 p-2 text-xs text-white outline-none focus:border-sky-400" /><button disabled={busyId === alert.id} onClick={() => modify(alert.id)} className="mt-2 rounded bg-sky-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-sky-500 disabled:opacity-50">Save changes</button></div>}<div className="mt-3 grid grid-cols-2 gap-2"><button disabled={busyId === alert.id} onClick={() => review(alert.id, "approved")} className="flex items-center justify-center gap-1 rounded bg-emerald-600 px-2 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"><Check className="h-3.5 w-3.5" /> Approve</button><button disabled={busyId === alert.id} onClick={() => review(alert.id, "dismissed")} className="flex items-center justify-center gap-1 rounded bg-slate-700 px-2 py-2 text-xs font-semibold text-white hover:bg-slate-600 disabled:opacity-50"><XCircle className="h-3.5 w-3.5" /> Dismiss</button><button onClick={() => { setEditingId(editingId === alert.id ? null : alert.id); setEditedDescription(alert.description ?? ""); }} className="rounded border border-sky-500/40 px-2 py-2 text-xs text-sky-200 hover:bg-sky-500/10">Modify</button><a href={`/api/alerts/${alert.id}/cap.xml`} target="_blank" rel="noreferrer" className="flex items-center justify-center gap-1 rounded border border-slate-600 px-2 py-2 text-xs text-slate-200 hover:bg-slate-800"><FileCode2 className="h-3.5 w-3.5" /> CAP XML</a></div></article>)}
        {approvedAlerts.length > 0 && <section className="mt-4 border-t border-slate-700 pt-3"><h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">Authorised for dissemination</h3>{approvedAlerts.slice(0, 3).map((alert) => <article key={alert.id} className="mb-2 rounded-lg border border-emerald-400/20 bg-emerald-500/5 p-3"><div className="text-sm font-medium text-white">{alert.title}</div><div className="mt-2 grid grid-cols-2 gap-2"><a href={`/api/alerts/${alert.id}/cap.xml`} target="_blank" rel="noreferrer" className="flex items-center justify-center gap-1 rounded border border-slate-600 px-2 py-2 text-xs text-slate-200 hover:bg-slate-800"><FileCode2 className="h-3.5 w-3.5" /> CAP XML</a><button disabled={busyId === alert.id} onClick={() => broadcast(alert.id)} className="flex items-center justify-center gap-1 rounded border border-amber-500/50 px-2 py-2 text-xs text-amber-200 hover:bg-amber-500/10 disabled:opacity-50"><Radio className="h-3.5 w-3.5" /> Broadcast</button></div></article>)}</section>}
      </div>
    </Panel>
  );
}
