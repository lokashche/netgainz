"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";

export default function ScheduleEditor({
  allocationDays,
  autoCreate,
  nextSweepDate,
}: {
  allocationDays: string;
  autoCreate: boolean;
  nextSweepDate: string | null;
}) {
  const router = useRouter();
  const [days, setDays] = useState(allocationDays);
  const [auto, setAuto] = useState(autoCreate);
  const [next, setNext] = useState(nextSweepDate);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const res = await fetch("/api/profit-first/schedule", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allocation_days: days, sweep_auto_create: auto }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setBusy(false);
        return;
      }
      // server normalises the day list and returns the cleaned values
      if (body?.allocation_days) setDays(body.allocation_days);
      if (body?.next_sweep_date) setNext(body.next_sweep_date);
      setMsg("Schedule saved.");
      setBusy(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setBusy(false);
    }
  }

  return (
    <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]">
            Allocation Days
          </label>
          <input
            type="text"
            value={days}
            onChange={(e) => setDays(e.target.value)}
            placeholder="10, 25"
            className="w-40 px-3 py-2 rounded-lg text-sm bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] focus:outline-none focus:ring-2 focus:ring-[#22D38C]"
          />
          <p className="text-[#8A97B2] text-xs mt-1">
            Days of the month (Profit First suggests 10 &amp; 25 — choose any).
          </p>
        </div>

        <label className="flex items-center gap-2 text-sm text-[#E6EDF7] pb-1 cursor-pointer">
          <input
            type="checkbox"
            checked={auto}
            onChange={(e) => setAuto(e.target.checked)}
            className="accent-[#22D38C] w-4 h-4"
          />
          Auto-create draft on schedule
        </label>

        <button
          type="button"
          onClick={save}
          disabled={busy}
          className="bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] font-medium rounded-lg py-2 px-4 text-sm hover:bg-[#22304d] disabled:opacity-50 transition-colors"
        >
          {busy ? "Saving…" : "Save schedule"}
        </button>

        <div className="ml-auto text-right">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider">Next sweep</p>
          <p className="text-[#E6EDF7] text-sm font-medium">{next ?? "—"}</p>
        </div>
      </div>
      {msg && <p className="text-[#22D38C] text-xs mt-2">{msg}</p>}
      {error && <p className="text-[#F87171] text-xs mt-2">{error}</p>}
    </div>
  );
}
