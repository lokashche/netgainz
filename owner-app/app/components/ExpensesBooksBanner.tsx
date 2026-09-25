"use client";

import { useEffect, useState } from "react";

// Stage 11.0: expenses saved before they started going into the books. Posting
// them is the owner's call — an accountant may already have them elsewhere — so it
// is a button, never automatic. Owner-only on the backend; staff see nothing.
export default function ExpensesBooksBanner() {
  const [count, setCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => {
    fetch("/api/expenses/books")
      .then((res) => (res.ok ? res.json() : null))
      .then((body: { count?: number } | null) => setCount(body?.count ?? 0))
      .catch(() => {});
  }, []);

  if (!count && !note) return null;

  async function putInBooks() {
    setBusy(true);
    try {
      const res = await fetch("/api/expenses/books", { method: "POST" });
      const body = (await res.json().catch(() => null)) as
        | { posted?: number; skipped?: { date: string; reason: string }[] }
        | null;
      const skipped = body?.skipped ?? [];
      setNote(
        res.ok
          ? `${body?.posted ?? 0} expense${body?.posted === 1 ? "" : "s"} put in your books.` +
              (skipped.length ? ` ${skipped.length} could not go in yet: ${skipped[0].reason}` : "")
          : `That did not run (${res.status}).`
      );
      setCount(skipped.length);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-[rgba(251,191,36,0.4)] bg-[rgba(251,191,36,0.06)] px-4 py-3 mb-4 text-sm flex flex-wrap items-center justify-between gap-3">
      <p className="text-[#FBBF24]">
        {note ||
          `${count} expense${count === 1 ? " isn't" : "s aren't"} in your accounts yet, so your official Profit & Loss leaves ${count === 1 ? "it" : "them"} out.`}
      </p>
      {count > 0 && !note && (
        <button
          type="button"
          onClick={putInBooks}
          disabled={busy}
          className="bg-[#FBBF24] text-[#0B1220] font-semibold rounded-lg py-2 px-4 text-sm disabled:opacity-50"
        >
          {busy ? "Putting them in…" : "Put them in my books"}
        </button>
      )}
    </div>
  );
}
