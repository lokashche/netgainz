"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { Collections, DueRow } from "@/lib/types";

// Who owes money, and how late.
//
// One row per unpaid PART, not per member. A quarterly fee split three ways is three
// promises, and a member who has missed two of them belongs here twice — the thing the
// dashboard's single overdue row cannot say. This is where the daily money reminder
// points, and where a payment gets taken.

const PAYMENT_MODES = ["Cash", "UPI", "Card", "Bank Transfer", "Online"];

function money(n: number): string {
  return `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtDate(v: string): string {
  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? v
    : d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function Collect({ row, onDone }: { row: DueRow; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState(String(row.outstanding));
  const [mode, setMode] = useState("Cash");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(
        `/api/subscriptions/${encodeURIComponent(row.membership)}/payment`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ amount: Number(amount), payment_mode: mode }),
        }
      );
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { message?: string; error?: string };
        throw new Error(body.message ?? body.error ?? `That did not save (${res.status}).`);
      }
      setOpen(false);
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not save.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="px-3 py-1.5 rounded-md text-xs font-semibold bg-[#22D38C] text-[#0B1220] hover:bg-[#1CB877]"
      >
        Collect
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2 flex-wrap justify-end">
      <input
        type="number"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="w-24 px-2 py-1.5 rounded-md text-xs bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7]"
        aria-label="Amount"
      />
      <select
        value={mode}
        onChange={(e) => setMode(e.target.value)}
        className="px-2 py-1.5 rounded-md text-xs bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7]"
        aria-label="Payment mode"
      >
        {PAYMENT_MODES.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={submit}
        disabled={busy}
        className="px-3 py-1.5 rounded-md text-xs font-semibold bg-[#22D38C] text-[#0B1220] disabled:opacity-40"
      >
        {busy ? "…" : "Save"}
      </button>
      <button
        type="button"
        onClick={() => {
          setOpen(false);
          setError("");
        }}
        className="px-2 py-1.5 rounded-md text-xs text-[#8A97B2] hover:text-[#E6EDF7]"
      >
        Cancel
      </button>
      {error && <p className="w-full text-right text-xs text-[#F87171]">{error}</p>}
    </div>
  );
}

function Bucket({
  title,
  accent,
  blurb,
  rows,
  total,
  showLate,
  onDone,
}: {
  title: string;
  accent: string;
  blurb: string;
  rows: DueRow[];
  total: number;
  showLate: boolean;
  onDone: () => void;
}) {
  if (!rows.length) return null;
  return (
    <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden mb-6">
      <div
        className="px-4 py-3 border-b border-[#1E2D45] flex items-baseline justify-between gap-3 flex-wrap"
        style={{ backgroundColor: `${accent}1F` }}
      >
        <div>
          <h2 className="text-sm font-semibold" style={{ color: accent }}>
            {title} ({rows.length})
          </h2>
          <p className="text-[#8A97B2] text-xs mt-0.5">{blurb}</p>
        </div>
        <span className="text-lg font-bold text-[#E6EDF7] tabular-nums">{money(total)}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
              <th className="text-left font-medium px-4 py-3">Member</th>
              <th className="text-left font-medium px-4 py-3">Due</th>
              {showLate && (
                <th className="hidden sm:table-cell text-left font-medium px-4 py-3">Late by</th>
              )}
              <th className="text-right font-medium px-4 py-3">Owed</th>
              <th className="text-right font-medium px-4 py-3">Take payment</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={`${r.membership}-${r.due_date}-${i}`}
                className="border-b border-[#1E2D45] last:border-0"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/subscriptions/${encodeURIComponent(r.membership)}`}
                    className="text-[#E6EDF7] hover:text-[#22D38C]"
                  >
                    {r.member_name ?? r.member}
                  </Link>
                  {r.membership_plan && (
                    <span className="text-[#8A97B2] text-xs"> · {r.membership_plan}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-[#8A97B2] whitespace-nowrap">
                  {fmtDate(r.due_date)}
                </td>
                {showLate && (
                  <td
                    className="hidden sm:table-cell px-4 py-3 whitespace-nowrap"
                    style={{ color: accent }}
                  >
                    {r.days_late} days
                  </td>
                )}
                <td className="px-4 py-3 text-right text-[#E6EDF7] tabular-nums whitespace-nowrap">
                  {money(r.outstanding)}
                </td>
                <td className="px-4 py-3 text-right">
                  <Collect row={r} onDone={onDone} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function CollectionsPage() {
  const [data, setData] = useState<Collections | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/collections");
      if (!res.ok) throw new Error(`Could not read what is owed (${res.status}).`);
      setData((await res.json()) as Collections);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read what is owed.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const nothingOwed =
    data && !data.late.length && !data.due_today.length && !data.due_soon.length;

  return (
    <div>
      <h1 className="text-2xl font-bold text-[#E6EDF7] mb-1">Money to collect</h1>
      <p className="text-[#8A97B2] text-sm mb-6">
        One line per payment, not per member — someone paying in parts owes you several
        times over.
      </p>

      {error && (
        <div className="mb-4 rounded-lg px-4 py-3 bg-[rgba(248,113,113,0.08)] text-[#F87171] text-sm">
          {error}
        </div>
      )}

      {loading && !error && <p className="text-[#8A97B2] text-sm">Loading…</p>}

      {nothingOwed && (
        <div className="bg-[rgba(34,211,140,0.06)] border border-[rgba(34,211,140,0.25)] rounded-xl p-6">
          <p className="text-[#22D38C] font-semibold text-sm">Nothing outstanding.</p>
          <p className="text-[#8A97B2] text-sm mt-1">
            Every payment due so far has been collected.
          </p>
        </div>
      )}

      {data && (
        <>
          <Bucket
            title="Late"
            accent="#F87171"
            blurb="Past their due date. Chase these first."
            rows={data.late}
            total={data.total_late}
            showLate
            onDone={load}
          />
          <Bucket
            title="Due today"
            accent="#FBBF24"
            blurb="Payable today."
            rows={data.due_today}
            total={data.total_due_today}
            showLate={false}
            onDone={load}
          />
          <Bucket
            title={`Coming up (next ${data.within_days} days)`}
            accent="#5EEAD4"
            blurb="Not owed yet — here so nothing takes you by surprise."
            rows={data.due_soon}
            total={data.total_due_soon}
            showLate={false}
            onDone={load}
          />
        </>
      )}
    </div>
  );
}
