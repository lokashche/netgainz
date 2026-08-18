"use client";

import { useCallback, useEffect, useState } from "react";
import type { RepeatingExpenses } from "@/lib/types";

// Expenses the owner marked as repeating, and the periods still waiting.
//
// They are raised as DRAFTS overnight — rent is the same every month but electricity
// is not, so the owner checks the amount and submits. This banner exists so the
// waiting ones are visible during the day rather than only after the job has run.

function money(n: number): string {
  return `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export default function RepeatingExpensesBanner() {
  const [data, setData] = useState<RepeatingExpenses | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/expenses/repeating");
      if (!res.ok) return; // never block the expenses list on this
      setData((await res.json()) as RepeatingExpenses);
    } catch {
      /* same — the list matters more than the banner */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const raiseNow = async () => {
    setBusy(true);
    setError("");
    setNote("");
    try {
      const res = await fetch("/api/expenses/repeating", { method: "POST" });
      if (!res.ok) throw new Error(`That did not run (${res.status}).`);
      const body = (await res.json()) as { created: number; skipped: number };
      setNote(
        body.created
          ? `${body.created} draft${body.created === 1 ? "" : "s"} added below. Check the amounts, then submit.`
          : "Nothing was waiting."
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not run.");
    } finally {
      setBusy(false);
    }
  };

  if (!data || !data.due_now) return null;

  const skipped = data.rows.reduce((n, r) => n + r.skipped, 0);

  return (
    <div className="mb-6 rounded-xl border border-[rgba(94,234,212,0.3)] bg-[rgba(94,234,212,0.05)] p-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p className="text-[#5EEAD4] font-semibold text-sm">
            {data.due_now} repeating expense{data.due_now === 1 ? "" : "s"} waiting
          </p>
          <ul className="mt-2 space-y-1">
            {data.rows
              .filter((r) => r.due.length)
              .slice(0, 5)
              .map((r) => (
                <li key={r.root} className="text-xs text-[#8A97B2]">
                  <span className="text-[#E6EDF7]">{r.category ?? r.root}</span>
                  {r.vendor ? ` · ${r.vendor}` : ""} · {money(r.amount)} ·{" "}
                  {r.due.length} {r.frequency.toLowerCase()} period
                  {r.due.length === 1 ? "" : "s"} since {r.last_raised}
                </li>
              ))}
          </ul>
          {skipped > 0 && (
            <p className="mt-2 text-xs text-[#FBBF24]">
              {skipped} older period{skipped === 1 ? " is" : "s are"} further back than the
              catch-up limit and will not be raised. Add those by hand if you need them.
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={raiseNow}
          disabled={busy}
          className="px-4 py-2 rounded-lg text-sm font-semibold bg-[#22D38C] text-[#0B1220] hover:bg-[#1CB877] disabled:opacity-40 whitespace-nowrap"
        >
          {busy ? "Adding…" : "Add them now"}
        </button>
      </div>
      <p className="mt-3 text-xs text-[#8A97B2]">
        These are added as drafts for you to check and submit — nothing reaches your
        accounts on its own.
      </p>
      {note && <p className="mt-2 text-xs text-[#22D38C]">{note}</p>}
      {error && <p className="mt-2 text-xs text-[#F87171]">{error}</p>}
    </div>
  );
}
