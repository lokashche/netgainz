"use client";

import { useState, useEffect, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { extractFrappeError } from "@/lib/frappe";
import type { CoachCommissionRun } from "@/lib/types";

type Params = Promise<{ id: string }>;

function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `₹${Number(v).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function CommissionRunDetailPage({ params }: { params: Params }) {
  const { id } = use(params);
  const router = useRouter();

  const [run, setRun] = useState<CoachCommissionRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/commissions/runs/${encodeURIComponent(id)}`);
      const body = (await res.json().catch(() => ({}))) as { data?: CoachCommissionRun };
      if (!res.ok || !body.data) {
        setError(`Failed to load run (${res.status})`);
        return;
      }
      setRun(body.data);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function action(kind: "approve" | "cancel") {
    const verb = kind === "approve" ? "approve" : "cancel";
    if (
      !confirm(
        kind === "approve"
          ? run?.post_to_ledger
            ? "Approve this run? It posts a balanced Journal Entry to the ledger for the coach commissions."
            : "Approve this run? It records the commissions with no ledger movement."
          : "Cancel this run? Any Journal Entry it posted will be reversed."
      )
    )
      return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/commissions/runs/${encodeURIComponent(id)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: kind === "cancel" ? JSON.stringify({ action: "cancel" }) : JSON.stringify({}),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Could not ${verb} (${res.status})`);
        setBusy(false);
        return;
      }
      await load();
      setBusy(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setBusy(false);
    }
  }

  async function discard() {
    if (!confirm("Discard this draft run?")) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/commissions/runs/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Could not discard (${res.status})`);
        setBusy(false);
        return;
      }
      router.push("/commissions");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="text-[#8A97B2] text-sm">Loading…</p>;
  }
  if (!run) {
    return (
      <div>
        <p className="text-[#F87171] text-sm">{error ?? "Run not found"}</p>
        <Link href="/commissions" className="text-[#22D38C] text-sm hover:underline">
          ← Back to Coach Commissions
        </Link>
      </div>
    );
  }

  const isDraft = run.docstatus === 0;
  const isPosted = run.docstatus === 1;
  const isCancelled = run.docstatus === 2;
  const statusLabel = isPosted ? "Posted" : isCancelled ? "Cancelled" : "Draft";
  const statusColor = isPosted
    ? "text-[#22D38C]"
    : isCancelled
    ? "text-[#F87171]"
    : "text-[#8A97B2]";
  const lines = run.lines ?? [];

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-4">
        <Link
          href="/commissions"
          className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors"
        >
          ← Back to Coach Commissions
        </Link>
      </div>

      <div className="flex items-end justify-between flex-wrap gap-3 mb-5">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">{run.name}</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            {run.period_start ?? "—"} → {run.period_end ?? "—"} · basis:{" "}
            {run.percentage_basis ?? "—"} ·{" "}
            {run.post_to_ledger ? "posts to ledger" : "record-only"} ·{" "}
            <span className={statusColor}>{statusLabel}</span>
          </p>
        </div>
        <div className="text-right">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider">Total Commission</p>
          <p className="text-2xl font-bold text-[#E6EDF7]">{money(run.total_commission)}</p>
        </div>
      </div>

      {error && (
        <div className="bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm mb-4">
          {error}
        </div>
      )}

      {isDraft && (
        <div className="bg-[rgba(245,179,90,0.06)] border border-[rgba(245,179,90,0.3)] rounded-xl p-3 mb-4 text-sm text-[#F5B35A]">
          Draft only — nothing has been recorded. Review the lines below, then Approve.
        </div>
      )}

      <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden mb-5">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                <th className="text-left font-medium px-4 py-3">Coach</th>
                <th className="text-left font-medium px-4 py-3">Type</th>
                <th className="text-left font-medium px-4 py-3">Basis</th>
                <th className="text-right font-medium px-4 py-3">Base</th>
                <th className="text-right font-medium px-4 py-3">Rate</th>
                <th className="text-right font-medium px-4 py-3">Commission</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => (
                <tr
                  key={`${l.coach}-${i}`}
                  className="border-b border-[#1A2540] last:border-0"
                >
                  <td className="px-4 py-3 text-[#E6EDF7] font-medium">{l.coach}</td>
                  <td className="px-4 py-3 text-[#8A97B2]">{l.commission_type ?? "—"}</td>
                  <td className="px-4 py-3 text-[#8A97B2]">{l.basis_label ?? "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#8A97B2]">
                    {money(l.base_amount)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#8A97B2]">
                    {l.rate ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#E6EDF7]">
                    {money(l.commission_amount)}
                  </td>
                </tr>
              ))}
              <tr className="border-t border-[#1E2D45] bg-[#0E1626]">
                <td className="px-4 py-3 text-[#8A97B2]" colSpan={5}>
                  Total
                </td>
                <td className="px-4 py-3 text-right tabular-nums font-semibold text-[#E6EDF7]">
                  {money(run.total_commission)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {isPosted &&
        (run.journal_entry ? (
          <p className="text-sm text-[#8A97B2] mb-5">
            Posted as Journal Entry{" "}
            <span className="text-[#E6EDF7] font-medium">{run.journal_entry}</span>.
          </p>
        ) : (
          <p className="text-sm text-[#8A97B2] mb-5">Recorded (no ledger entry).</p>
        ))}

      <div className="flex flex-wrap gap-3">
        {isDraft && (
          <>
            <button
              type="button"
              onClick={() => action("approve")}
              disabled={busy}
              className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
            >
              {busy ? "Approving…" : "Approve"}
            </button>
            <button
              type="button"
              onClick={discard}
              disabled={busy}
              className="border border-[#1E2D45] text-[#8A97B2] rounded-lg py-2 px-4 text-sm hover:text-[#E6EDF7] hover:bg-[#1A2540] disabled:opacity-50 transition-colors"
            >
              Discard
            </button>
          </>
        )}
        {isPosted && (
          <button
            type="button"
            onClick={() => action("cancel")}
            disabled={busy}
            className="border border-[#F87171] text-[#F87171] rounded-lg py-2 px-4 text-sm hover:bg-[rgba(248,113,113,0.1)] disabled:opacity-50 transition-colors"
          >
            {busy ? "Cancelling…" : "Cancel run"}
          </button>
        )}
      </div>
    </div>
  );
}
