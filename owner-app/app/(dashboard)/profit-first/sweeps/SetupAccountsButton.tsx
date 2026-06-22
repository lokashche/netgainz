"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";

// Idempotently provisions the five Profit First ledger accounts. Safe to click
// more than once — it only creates accounts that don't already exist.
export default function SetupAccountsButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function setup() {
    if (
      !confirm(
        "Create the five Profit First accounts in your chart of accounts (Income + four allocation reserves) and map them? Safe to run more than once."
      )
    )
      return;
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const res = await fetch("/api/profit-first/setup-accounts", { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setBusy(false);
        return;
      }
      setMsg("Accounts ready.");
      setBusy(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={setup}
        disabled={busy}
        className="text-sm border border-[#1E2D45] text-[#8A97B2] rounded-lg py-2 px-4 hover:text-[#E6EDF7] hover:bg-[#1A2540] disabled:opacity-50 transition-colors"
      >
        {busy ? "Setting up…" : "Set up accounts"}
      </button>
      {msg && <p className="text-[#22D38C] text-xs">{msg}</p>}
      {error && <p className="text-[#F87171] text-xs">{error}</p>}
    </div>
  );
}
