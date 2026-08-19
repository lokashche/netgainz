"use client";

// OP-4: the walk-in quick sale. Name + phone, cash/UPI, one tap — the invoice
// and its payment post server-side and the cash lands in Profit First.

import { useState, useEffect } from "react";
import { extractFrappeError } from "@/lib/frappe";
import type { DayPassSaleResult, GymSettings, TodaysDayPasses } from "@/lib/types";

const PAYMENT_MODES = ["Cash", "UPI", "Card", "Bank Transfer", "Online"];

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

function fmtMoney(v: number): string {
  return v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtTime(v: string): string {
  const d = new Date(v.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

export default function DayPassPage() {
  const [guestName, setGuestName] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [mode, setMode] = useState("Cash");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [todays, setTodays] = useState<TodaysDayPasses | null>(null);

  async function loadTodays() {
    const res = await fetch("/api/day-pass");
    if (res.ok) setTodays((await res.json()) as TodaysDayPasses | null);
  }

  useEffect(() => {
    (async () => {
      await loadTodays();
      // Prefill the tenant's configured day-pass price, if one is set.
      const res = await fetch("/api/settings");
      if (!res.ok) return;
      const body = (await res.json()) as { data?: GymSettings };
      const price = body.data?.day_pass_price;
      if (price && price > 0) setAmount(String(price));
    })();
  }, []);

  async function sell() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch("/api/day-pass", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          guest_name: guestName,
          phone: phone || null,
          amount: Number(amount),
          payment_mode: mode,
        }),
      });
      const body = (await res.json().catch(() => null)) as DayPassSaleResult | null;
      if (!res.ok || !body?.day_pass) {
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return;
      }
      setNotice(`${body.guest_name} — ₹${fmtMoney(body.amount)} received. Welcome in.`);
      setGuestName("");
      setPhone("");
      await loadTodays();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Day Pass</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          Walk-in drop-ins — one tap records the visit AND the money.
        </p>
      </div>

      {error && (
        <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171] mb-4">
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-lg bg-[rgba(34,211,140,0.1)] border border-[#22D38C] px-4 py-3 text-sm text-[#22D38C] mb-4">
          {notice}
        </div>
      )}

      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>
              Guest Name <span className="text-[#F87171]">*</span>
            </label>
            <input
              type="text"
              autoFocus
              value={guestName}
              onChange={(e) => setGuestName(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Phone</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>
              Amount <span className="text-[#F87171]">*</span>
            </label>
            <input
              type="number"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Payment Mode</label>
            <select value={mode} onChange={(e) => setMode(e.target.value)} className={inputClass}>
              {PAYMENT_MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button
          type="button"
          onClick={sell}
          disabled={busy || !guestName.trim() || !amount || Number(amount) <= 0}
          className="mt-4 bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
        >
          {busy ? "Selling…" : "Sell day pass"}
        </button>
      </div>

      <div className="mt-6 bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        <div className="px-4 py-3 border-b border-[#1E2D45] flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <h2 className="text-sm font-semibold text-[#E6EDF7]">
            Today ({todays?.count ?? 0})
          </h2>
          <span className="text-sm text-[#22D38C] tabular-nums">
            ₹{fmtMoney(todays?.total ?? 0)}
          </span>
        </div>
        {(todays?.passes.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-[#8A97B2]">No day passes sold today.</p>
        ) : (
          <ul className="divide-y divide-[#1A2540]">
            {todays?.passes.map((p) => (
              <li
                key={p.name}
                className="flex items-center justify-between px-4 py-2.5 text-sm"
              >
                <span className="text-[#E6EDF7] truncate mr-2">
                  {p.guest_name}
                  {p.phone ? <span className="text-xs text-[#8A97B2]"> · {p.phone}</span> : null}
                </span>
                <span className="text-[#8A97B2] text-xs shrink-0 tabular-nums">
                  ₹{fmtMoney(p.amount)} · {p.payment_mode} · {fmtTime(p.creation)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
