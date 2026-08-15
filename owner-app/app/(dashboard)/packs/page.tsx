"use client";

// OP-4: session packs — sell one, watch the balances burn down, manage the
// products. A sale is real money in one tap (invoice + payment, server-side);
// the balance is counted from the use log and cannot drift.

import { useState, useEffect, useCallback } from "react";
import { extractFrappeError } from "@/lib/frappe";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";
import type {
  Member,
  PackAlerts,
  PackBalanceRow,
  PackBalances,
  PackSaleResult,
  SessionPack,
  UseSessionResult,
} from "@/lib/types";

const PAYMENT_MODES = ["Cash", "UPI", "Card", "Bank Transfer", "Online"];

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

async function fetchMembers(q: string): Promise<LinkFieldOption[]> {
  const url = q ? `/api/members?q=${encodeURIComponent(q)}` : "/api/members";
  const res = await fetch(url);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: Member[] };
  return (body.data ?? []).map((m) => ({
    id: m.name,
    label: m.full_name,
    sub: m.phone || m.email || undefined,
  }));
}

function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

function fmtMoney(v: number): string {
  return v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function PacksPage() {
  const [products, setProducts] = useState<SessionPack[]>([]);
  const [balances, setBalances] = useState<PackBalances | null>(null);
  const [alerts, setAlerts] = useState<PackAlerts | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Sell form
  const [member, setMember] = useState("");
  const [memberLabel, setMemberLabel] = useState("");
  const [pack, setPack] = useState("");
  const [mode, setMode] = useState("Cash");
  const [price, setPrice] = useState("");

  // New product form (owner)
  const [showNewProduct, setShowNewProduct] = useState(false);
  const [npName, setNpName] = useState("");
  const [npSessions, setNpSessions] = useState("10");
  const [npValidity, setNpValidity] = useState("60");
  const [npPrice, setNpPrice] = useState("");

  const loadAll = useCallback(async () => {
    const [productsRes, balancesRes, alertsRes] = await Promise.all([
      fetch("/api/packs"),
      fetch("/api/packs/balances"),
      fetch("/api/packs/alerts"),
    ]);
    if (productsRes.ok) {
      const body = (await productsRes.json()) as { data?: SessionPack[] };
      setProducts(body.data ?? []);
    }
    if (balancesRes.ok) setBalances((await balancesRes.json()) as PackBalances | null);
    if (alertsRes.ok) setAlerts((await alertsRes.json()) as PackAlerts | null);
  }, []);

  useEffect(() => {
    (async () => {
      await loadAll();
    })();
  }, [loadAll]);

  const activeProducts = products.filter((p) => p.is_active === 1);
  const selected = products.find((p) => p.name === pack);

  async function sellPack() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const payload: Record<string, unknown> = {
        member,
        session_pack: pack,
        payment_mode: mode,
      };
      if (price !== "" && Number.isFinite(Number(price))) payload.price = Number(price);
      const res = await fetch("/api/packs/sell", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await res.json().catch(() => null)) as PackSaleResult | null;
      if (!res.ok || !body?.pack_purchase) {
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return;
      }
      setNotice(
        `${body.member_name ?? body.member}: ${body.sessions} sessions for ₹${fmtMoney(body.amount)}, valid till ${fmtDate(body.expires_on)}. Paid.`
      );
      setMember("");
      setMemberLabel("");
      setPrice("");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setBusy(false);
    }
  }

  async function burnSession(row: PackBalanceRow) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch("/api/packs/use", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pack_purchase: row.pack_purchase }),
      });
      const body = (await res.json().catch(() => null)) as UseSessionResult | null;
      if (!res.ok || !body) {
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return;
      }
      setNotice(
        `${row.member_name ?? row.member}: session used — ${body.remaining} of ${body.total} left.`
      );
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setBusy(false);
    }
  }

  async function createProduct() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/packs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pack_name: npName,
          sessions: Number(npSessions) || 0,
          validity_days: Number(npValidity) || 0,
          price: Number(npPrice) || 0,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      setShowNewProduct(false);
      setNpName("");
      setNpPrice("");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setBusy(false);
    }
  }

  async function toggleProduct(p: SessionPack) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/packs/${encodeURIComponent(p.name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: p.is_active === 1 ? 0 : 1 }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      await loadAll();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Session Packs</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          PT packs sold as real invoices — the cash flows straight into Profit First.
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

      {/* Alerts */}
      {(alerts?.alert_count ?? 0) > 0 && (
        <div className="mb-6 bg-[rgba(251,191,36,0.05)] border border-[rgba(251,191,36,0.3)] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1E2D45]">
            <h2 className="text-sm font-semibold text-[#FBBF24]">
              Worth a word ({alerts?.alert_count})
            </h2>
          </div>
          <ul className="divide-y divide-[#1A2540]">
            {alerts?.alerts.map((a) => (
              <li
                key={a.pack_purchase}
                className="flex items-center justify-between flex-wrap gap-2 px-4 py-2.5 text-sm"
              >
                <span className="text-[#E6EDF7]">
                  {a.member_name ?? a.member}
                  <span className="text-xs text-[#8A97B2] ml-2">{a.session_pack}</span>
                </span>
                <span className="text-xs text-[#FBBF24] shrink-0">
                  {a.low_balance ? `${a.remaining} session(s) left` : ""}
                  {a.low_balance && a.expiring ? " · " : ""}
                  {a.expiring ? `expires ${fmtDate(a.expires_on)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Sell */}
      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 mb-6">
        <h2 className="text-sm font-semibold text-[#E6EDF7] mb-4">Sell a pack</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className={labelClass}>Member</label>
            <LinkFieldPicker
              value={member}
              displayLabel={memberLabel}
              onChange={(id, label) => {
                setMember(id);
                setMemberLabel(label);
              }}
              fetchOptions={fetchMembers}
              placeholder="Search members…"
              emptyHint="No members found"
              inputClassName={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Pack</label>
            <select value={pack} onChange={(e) => setPack(e.target.value)} className={inputClass}>
              <option value="">Select a pack…</option>
              {activeProducts.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.pack_name} — {p.sessions} × ₹{p.price}
                </option>
              ))}
            </select>
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
          <div>
            <label className={labelClass}>Price (optional)</label>
            <input
              type="number"
              min="0"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder={selected ? `₹${selected.price}` : "Pack price"}
              className={inputClass}
            />
          </div>
        </div>
        <button
          type="button"
          onClick={sellPack}
          disabled={busy || !member || !pack}
          className="mt-4 bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
        >
          {busy ? "Selling…" : "Sell — invoice & payment in one go"}
        </button>
      </div>

      {/* Balances */}
      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden mb-6">
        <div className="px-4 py-3 border-b border-[#1E2D45]">
          <h2 className="text-sm font-semibold text-[#E6EDF7]">
            Active packs ({balances?.active_count ?? 0})
          </h2>
        </div>
        {(balances?.active.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-[#8A97B2]">No packs in play.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                  <th className="text-left font-medium px-4 py-3">Member</th>
                  <th className="text-left font-medium px-4 py-3">Pack</th>
                  <th className="text-left font-medium px-4 py-3">Balance</th>
                  <th className="text-left font-medium px-4 py-3">Expires</th>
                  <th className="text-right font-medium px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {balances?.active.map((r) => (
                  <tr
                    key={r.pack_purchase}
                    className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
                  >
                    <td className="px-4 py-3 text-[#E6EDF7]">{r.member_name ?? r.member}</td>
                    <td className="px-4 py-3 text-[#8A97B2]">{r.session_pack}</td>
                    <td className="px-4 py-3 text-[#E6EDF7] tabular-nums">
                      {r.remaining} / {r.total}
                    </td>
                    <td className="px-4 py-3 text-[#8A97B2]">
                      {fmtDate(r.expires_on)}
                      <span className="text-xs"> · {r.days_left}d</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => burnSession(r)}
                        disabled={busy}
                        className="text-xs border border-[#22D38C] text-[#22D38C] rounded-lg py-1.5 px-3 hover:bg-[rgba(34,211,140,0.1)] disabled:opacity-40 transition-colors"
                      >
                        Use session
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Products */}
      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        <div className="px-4 py-3 border-b border-[#1E2D45] flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#E6EDF7]">Pack products</h2>
          <button
            type="button"
            onClick={() => setShowNewProduct((v) => !v)}
            className="text-xs text-[#22D38C] hover:underline"
          >
            {showNewProduct ? "Close" : "+ New pack"}
          </button>
        </div>

        {showNewProduct && (
          <div className="px-4 py-4 border-b border-[#1E2D45] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-2">
              <label className={labelClass}>Name</label>
              <input
                type="text"
                value={npName}
                onChange={(e) => setNpName(e.target.value)}
                placeholder="10 PT Sessions"
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Sessions</label>
              <input type="number" min="1" value={npSessions} onChange={(e) => setNpSessions(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Validity (days)</label>
              <input type="number" min="1" value={npValidity} onChange={(e) => setNpValidity(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Price</label>
              <input type="number" min="0" value={npPrice} onChange={(e) => setNpPrice(e.target.value)} className={inputClass} />
            </div>
            <div className="lg:col-span-5">
              <button
                type="button"
                onClick={createProduct}
                disabled={busy || !npName || !npPrice}
                className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-4 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
              >
                {busy ? "Saving…" : "Save pack"}
              </button>
            </div>
          </div>
        )}

        {products.length === 0 ? (
          <p className="p-8 text-center text-sm text-[#8A97B2]">
            No packs defined yet — create one to start selling PT.
          </p>
        ) : (
          <ul className="divide-y divide-[#1A2540]">
            {products.map((p) => (
              <li
                key={p.name}
                className="flex items-center justify-between flex-wrap gap-2 px-4 py-2.5 text-sm"
              >
                <span className={p.is_active === 1 ? "text-[#E6EDF7]" : "text-[#8A97B2] line-through"}>
                  {p.pack_name}
                  <span className="text-xs text-[#8A97B2] ml-2 no-underline">
                    {p.sessions} sessions · {p.validity_days} days · ₹{fmtMoney(p.price)}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => toggleProduct(p)}
                  disabled={busy}
                  className="text-xs text-[#8A97B2] hover:text-[#E6EDF7] underline disabled:opacity-40"
                >
                  {p.is_active === 1 ? "Stop selling" : "Sell again"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
