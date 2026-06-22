"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { extractFrappeError } from "@/lib/frappe";
import type { PFSweep } from "@/lib/types";

function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `₹${Number(v).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function SweepDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [sweep, setSweep] = useState<PFSweep | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/profit-first/sweeps/${encodeURIComponent(id)}`);
      const body = (await res.json().catch(() => ({}))) as { data?: PFSweep };
      if (!res.ok || !body.data) {
        setError(`Failed to load sweep (${res.status})`);
        return;
      }
      setSweep(body.data);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function action(kind: "approve" | "cancel") {
    const verb = kind === "approve" ? "approve and post" : "cancel";
    if (
      !confirm(
        kind === "approve"
          ? "Approve this sweep? It posts a Journal Entry to the ledger and moves money between your Profit First accounts."
          : "Cancel this sweep? Its Journal Entry will be reversed."
      )
    )
      return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/profit-first/sweeps/${encodeURIComponent(id)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: kind }),
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
    if (!confirm("Discard this draft proposal?")) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/profit-first/sweeps/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Could not discard (${res.status})`);
        setBusy(false);
        return;
      }
      router.push("/profit-first/sweeps");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="text-[#8A97B2] text-sm">Loading…</p>;
  }
  if (!sweep) {
    return (
      <div>
        <p className="text-[#F87171] text-sm">{error ?? "Sweep not found"}</p>
        <Link href="/profit-first/sweeps" className="text-[#22D38C] text-sm hover:underline">
          ← Back to Sweeps
        </Link>
      </div>
    );
  }

  const isDraft = sweep.docstatus === 0;
  const isPosted = sweep.docstatus === 1;
  const isCancelled = sweep.docstatus === 2;
  const statusLabel = isPosted ? "Posted" : isCancelled ? "Cancelled" : "Draft";
  const statusColor = isPosted
    ? "text-[#22D38C]"
    : isCancelled
    ? "text-[#F87171]"
    : "text-[#8A97B2]";

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-4">
        <Link
          href="/profit-first/sweeps"
          className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors"
        >
          ← Back to Sweeps
        </Link>
      </div>

      <div className="flex items-end justify-between flex-wrap gap-3 mb-5">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">{sweep.name}</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            {sweep.assessment_window} · {sweep.period_label} · Tier {sweep.tier_code ?? "—"} ·{" "}
            <span className={statusColor}>{statusLabel}</span>
          </p>
        </div>
        <div className="text-right">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider">Real Revenue</p>
          <p className="text-2xl font-bold text-[#E6EDF7]">{money(sweep.real_revenue)}</p>
        </div>
      </div>

      {error && (
        <div className="bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm mb-4">
          {error}
        </div>
      )}

      {isDraft && (
        <div className="bg-[rgba(245,179,90,0.06)] border border-[rgba(245,179,90,0.3)] rounded-xl p-3 mb-4 text-sm text-[#F5B35A]">
          Proposal only — no money has moved. Review the split below, then Approve &amp; Post.
        </div>
      )}

      <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden mb-5">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                <th className="text-left font-medium px-4 py-3">Account</th>
                <th className="text-left font-medium px-4 py-3">Ledger</th>
                <th className="text-right font-medium px-4 py-3">Target %</th>
                <th className="text-right font-medium px-4 py-3">Amount</th>
              </tr>
            </thead>
            <tbody>
              {(sweep.allocations ?? []).map((a) => (
                <tr key={a.account_role} className="border-b border-[#1A2540] last:border-0">
                  <td className="px-4 py-3 text-[#E6EDF7] font-medium">{a.account_role}</td>
                  <td className="px-4 py-3 text-[#8A97B2]">{a.pf_account ?? "— unmapped —"}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#8A97B2]">
                    {a.target_pct != null ? `${Number(a.target_pct).toFixed(2)}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#E6EDF7]">
                    {money(a.amount)}
                  </td>
                </tr>
              ))}
              <tr className="border-t border-[#1E2D45] bg-[#0E1626]">
                <td className="px-4 py-3 text-[#8A97B2]" colSpan={3}>
                  Credited to {sweep.income_account ?? "Income"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums font-semibold text-[#E6EDF7]">
                  {money(sweep.real_revenue)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {isPosted && sweep.journal_entry && (
        <p className="text-sm text-[#8A97B2] mb-5">
          Posted as Journal Entry{" "}
          <span className="text-[#E6EDF7] font-medium">{sweep.journal_entry}</span>.
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        {isDraft && (
          <>
            <button
              type="button"
              onClick={() => action("approve")}
              disabled={busy}
              className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
            >
              {busy ? "Posting…" : "Approve & Post"}
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
            {busy ? "Cancelling…" : "Cancel sweep"}
          </button>
        )}
      </div>
    </div>
  );
}
