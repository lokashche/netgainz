"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";

export default function NewSweepButton() {
  const router = useRouter();
  const [window, setWindow] = useState("Trailing 12 Months");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/profit-first/sweeps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ window }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || !body?.name) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setBusy(false);
        return;
      }
      router.push(`/profit-first/sweeps/${body.name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        <select
          value={window}
          onChange={(e) => setWindow(e.target.value)}
          disabled={busy}
          className="text-sm bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#22D38C]"
        >
          <option value="Trailing 12 Months">Trailing 12 Months</option>
          <option value="This Month">This Month</option>
        </select>
        <button
          type="button"
          onClick={create}
          disabled={busy}
          className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-4 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
        >
          {busy ? "Creating…" : "New proposal"}
        </button>
      </div>
      {error && <p className="text-[#F87171] text-xs">{error}</p>}
    </div>
  );
}
