"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";

// First and last day of the previous calendar month, as YYYY-MM-DD.
function prevMonthRange(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const end = new Date(now.getFullYear(), now.getMonth(), 0);
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate()
    ).padStart(2, "0")}`;
  return { start: iso(start), end: iso(end) };
}

export default function NewRunButton() {
  const router = useRouter();
  const defaults = prevMonthRange();
  const [periodStart, setPeriodStart] = useState(defaults.start);
  const [periodEnd, setPeriodEnd] = useState(defaults.end);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/commissions/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period_start: periodStart, period_end: periodEnd }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || !body?.name) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setBusy(false);
        return;
      }
      router.push(`/commissions/${body.name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        <input
          type="date"
          value={periodStart}
          onChange={(e) => setPeriodStart(e.target.value)}
          disabled={busy}
          className="text-sm bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#22D38C]"
        />
        <input
          type="date"
          value={periodEnd}
          onChange={(e) => setPeriodEnd(e.target.value)}
          disabled={busy}
          className="text-sm bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#22D38C]"
        />
        <button
          type="button"
          onClick={create}
          disabled={busy}
          className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-4 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
        >
          {busy ? "Creating…" : "New run"}
        </button>
      </div>
      {error && <p className="text-[#F87171] text-xs">{error}</p>}
    </div>
  );
}
