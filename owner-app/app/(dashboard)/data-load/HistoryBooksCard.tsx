"use client";

import { useEffect, useState } from "react";
import { extractFrappeError } from "@/lib/frappe";
import type { HistoryBooks } from "@/lib/types";

// Stage 12.2. The Subscriptions step loads billing history as records only, so the
// official books, the dashboard and Profit First read those months as zero. This
// card turns each loaded row into an invoice (what was charged) and a payment (what
// was paid), and shows month by month whether the books now match the gym's sheets.

const CARD = "bg-[#111A2E] border border-[#1E2D45] rounded-xl";

function rupees(n: number): string {
  return `₹${Math.round(n).toLocaleString("en-IN")}`;
}

function monthName(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleString("en-IN", { month: "short", year: "numeric" });
}

export default function HistoryBooksCard({ index }: { index: number }) {
  const [data, setData] = useState<HistoryBooks | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);

  const [version, setVersion] = useState(0);
  const refresh = () => setVersion((v) => v + 1);

  useEffect(() => {
    async function load() {
      const res = await fetch("/api/data-load/books");
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Could not read the books (${res.status}).`);
        return;
      }
      setData((body as { message: HistoryBooks }).message);
      setError("");
    }
    load();
  }, [version]);

  // Posting runs in the background; check again every few seconds until it is done.
  useEffect(() => {
    if (!data?.running) return;
    const t = setTimeout(() => setVersion((v) => v + 1), 3000);
    return () => clearTimeout(t);
  }, [data]);

  async function post() {
    setStarting(true);
    try {
      const res = await fetch("/api/data-load/books", { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) setError(extractFrappeError(body) ?? `Error ${res.status}`);
      refresh();
    } finally {
      setStarting(false);
    }
  }

  return (
    <section className={`${CARD} p-5 mb-4`}>
      <div className="flex items-start gap-3">
        <span className="flex-none w-7 h-7 rounded-full border border-[#1E2D45] text-[#8A97B2] text-xs font-semibold flex items-center justify-center">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[#E6EDF7] font-semibold">Past money into the books</h2>
          <p className="text-[#8A97B2] text-sm mt-1">
            Turns the subscriptions loaded above into invoices and payments, dated as in your
            sheets, so your reports, dashboard and Profit First see those months. What was not
            paid stays owed. Running it again adds nothing twice.
          </p>

          {error && <p className="mt-3 text-sm text-[#F87171]">{error}</p>}
          {!data && !error && <p className="mt-3 text-sm text-[#8A97B2]">Checking…</p>}

          {data && data.months.length === 0 && (
            <p className="mt-3 text-sm text-[#8A97B2]">No loaded subscriptions with money on them yet.</p>
          )}

          {data && data.months.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wider text-[#8A97B2]">
                    <th className="py-2 pr-3 font-medium">Month</th>
                    <th className="py-2 pr-3 font-medium text-right">Charged: sheet / books</th>
                    <th className="py-2 pr-3 font-medium text-right">Paid: sheet / books</th>
                    <th className="py-2 font-medium text-right">Check</th>
                  </tr>
                </thead>
                <tbody>
                  {data.months.map((m) => (
                    <tr key={m.month} className="border-t border-[#1E2D45] text-[#E6EDF7]">
                      <td className="py-2 pr-3 whitespace-nowrap">{monthName(m.month)}</td>
                      <td className="py-2 pr-3 text-right whitespace-nowrap">
                        {rupees(m.sheet_billed)} / {rupees(m.books_billed)}
                      </td>
                      <td className="py-2 pr-3 text-right whitespace-nowrap">
                        {rupees(m.sheet_paid)} / {rupees(m.books_paid)}
                      </td>
                      <td
                        className="py-2 text-right whitespace-nowrap"
                        style={{ color: m.matches ? "#22D38C" : "#FBBF24" }}
                      >
                        {m.matches ? "✓ Matches" : `${m.posted} of ${m.rows} in`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data && data.years_to_add.length > 0 && (
            <p className="mt-3 text-sm text-[#8A97B2]">
              Some of this history is before your first financial year. The missing year
              {data.years_to_add.length === 1 ? "" : "s"} (starting{" "}
              {data.years_to_add.join(", ")}) will be added for you.
            </p>
          )}

          {data && data.blocked.length > 0 && (
            <div className="mt-3 text-sm rounded-lg px-3 py-2 bg-[rgba(248,113,113,0.08)] text-[#F87171]">
              {data.blocked.length} row{data.blocked.length === 1 ? "" : "s"} will not go in:
              <ul className="mt-1 space-y-0.5 text-[#E6EDF7]">
                {data.blocked.slice(0, 10).map((b) => (
                  <li key={b.membership}>
                    {b.member} ({b.due_date}): {b.reason}
                  </li>
                ))}
                {data.blocked.length > 10 && <li>…and {data.blocked.length - 10} more</li>}
              </ul>
            </div>
          )}

          {data?.last_run && data.last_run.failed.length > 0 && !data.running && (
            <div className="mt-3 text-sm rounded-lg px-3 py-2 bg-[rgba(251,191,36,0.08)] text-[#FBBF24]">
              Last run: {data.last_run.posted} went in, {data.last_run.failed.length} did not:
              <ul className="mt-1 space-y-0.5 text-[#E6EDF7]">
                {data.last_run.failed.slice(0, 10).map((f, i) => (
                  <li key={i}>
                    {f.member} ({f.due_date}): {f.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {data && (
            <div className="mt-4">
              {data.running ? (
                <p className="text-sm text-[#5EEAD4]">Putting it into the books… you can leave this page open.</p>
              ) : data.pending > 0 ? (
                <button
                  type="button"
                  onClick={post}
                  disabled={starting}
                  className="px-4 py-2 rounded-lg text-sm font-semibold bg-[#22D38C] text-[#0B1220] disabled:opacity-40"
                >
                  {starting ? "Starting…" : `Put ${data.pending} row${data.pending === 1 ? "" : "s"} into the books`}
                </button>
              ) : (
                data.months.length > 0 && <p className="text-sm text-[#22D38C]">Nothing left to put in.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
