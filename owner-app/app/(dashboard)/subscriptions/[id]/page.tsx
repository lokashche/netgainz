"use client";

import { useState, useEffect, SyntheticEvent, use } from "react";
import { extractFrappeError } from "@/lib/frappe";
import { useRouter } from "next/navigation";
import type { Obligation, Subscription, SubscriptionStatus } from "@/lib/types";

type Params = Promise<{ id: string }>;

const PAYMENT_MODES = ["Cash", "UPI", "Card", "Bank Transfer", "Online"];

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const readonlyClass =
  "w-full px-3 py-2.5 rounded-lg text-sm bg-[#0B1220] border border-[#1E2D45] text-[#8A97B2]";

function statusBadge(status: SubscriptionStatus): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "Paid":
      return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
    case "Pending":
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    case "Overdue":
      return `${base} bg-[rgba(248,113,113,0.15)] text-[#F87171]`;
    case "Partial":
      return `${base} bg-[rgba(94,234,212,0.15)] text-[#5EEAD4]`;
    default: {
      const _exhaustive: never = status;
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2] /* ${_exhaustive} */`;
    }
  }
}

function formatCurrency(value?: number): string {
  if (value === undefined || value === null) return "—";
  return Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function SubscriptionDetailPage({ params }: { params: Params }) {
  const { id } = use(params);
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Read-only display fields
  const [subName, setSubName] = useState("");
  const [subStatus, setSubStatus] = useState<SubscriptionStatus>("Pending");
  const [balanceDue, setBalanceDue] = useState<number>(0);
  const [overdueDays, setOverdueDays] = useState<number>(0);
  const [memberName, setMemberName] = useState("");
  const [membershipPlan, setMembershipPlan] = useState("");
  const [month, setMonth] = useState("");
  const [tariff, setTariff] = useState<number>(0);
  const [nextRenewal, setNextRenewal] = useState("");

  // Derived from the membership's Sales Invoice — read-only (WP-11)
  const [collected, setCollected] = useState<number>(0);
  const [paid_date, setPaidDate] = useState("");
  const [due_date, setDueDate] = useState("");

  // Editable
  const [comments, setComments] = useState("");

  // Record-payment panel: posts a real Payment Entry (WP-11). Writing
  // fee_collected would record no revenue — Profit First and commissions read
  // collected cash from Payment Entries only.
  const [payAmount, setPayAmount] = useState("");
  const [payMode, setPayMode] = useState("");
  const [payDate, setPayDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);

  async function loadSub() {
    try {
      const res = await fetch(`/api/subscriptions/${encodeURIComponent(id)}`);
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const body = await res.json() as { data?: Subscription };
      const s = body.data;
      if (!s) throw new Error("Subscription not found");

      setSubName(s.name);
      setSubStatus(s.status);
      setBalanceDue(s.balance_due ?? 0);
      setOverdueDays(s.overdue_days ?? 0);
      setMemberName(s.member_name ?? s.member);
      setMembershipPlan(s.membership_plan ?? "");
      setMonth(s.month ?? "");
      setTariff(s.tariff ?? 0);
      setNextRenewal(s.next_renewal ?? "");

      setCollected((s.tariff ?? 0) - (s.balance_due ?? 0));
      setPaidDate(s.paid_date ?? "");
      setDueDate(s.due_date ?? "");
      setComments(s.comments ?? "");
      // Default the payment amount to whatever is still outstanding.
      setPayAmount(s.balance_due ? String(s.balance_due) : "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load subscription");
    } finally {
      setLoading(false);
    }
  }

  async function loadObligations() {
    try {
      const res = await fetch(
        `/api/subscriptions/${encodeURIComponent(id)}/obligations`
      );
      if (!res.ok) return;
      const body = (await res.json()) as {
        message?: { obligations?: Obligation[] };
      };
      setObligations(body.message?.obligations ?? []);
    } catch {
      // The schedule is supplementary — never block the page on it.
    }
  }

  useEffect(() => {
    loadSub();
    loadObligations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleRecordPayment() {
    setPaying(true);
    setPayError(null);
    try {
      const res = await fetch(
        `/api/subscriptions/${encodeURIComponent(id)}/payment`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            amount: Number(payAmount),
            payment_mode: payMode,
            posting_date: payDate,
          }),
        }
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setPayError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      // Re-fetch so the derived status / balance reflect the new Payment Entry.
      setLoading(true);
      await Promise.all([loadSub(), loadObligations()]);
    } catch (err) {
      setPayError(err instanceof Error ? err.message : "Failed to record payment");
    } finally {
      setPaying(false);
    }
  }

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(false);

    // WP-11: status / balance_due / due_date / next_renewal are all derived from
    // the Sales Invoice, and money is recorded as a Payment Entry — so the only
    // thing this form still writes is the note.
    const payload: Record<string, string | number> = { comments };

    try {
      const res = await fetch(`/api/subscriptions/${encodeURIComponent(id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
      } else {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        // Re-fetch to get updated calculated fields
        setLoading(true);
        await loadSub();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete subscription ${id}? This cannot be undone.`)) return;
    setDeleting(true);
    setError(null);

    try {
      const res = await fetch(`/api/subscriptions/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setDeleting(false);
        return;
      }

      router.push("/subscriptions");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-[#8A97B2] text-sm">
        Loading…
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/subscriptions" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Subscriptions
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Subscription</h1>
      </div>

      {/* Read-only info row */}
      <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-4 mb-6 flex flex-wrap items-center gap-4">
        <div>
          <p className="text-xs text-[#8A97B2] uppercase tracking-wider mb-1">Sub ID</p>
          <span className="font-mono text-[#5EEAD4] text-sm">{subName}</span>
        </div>
        <div>
          <p className="text-xs text-[#8A97B2] uppercase tracking-wider mb-1">Status</p>
          <span className={statusBadge(subStatus)}>{subStatus}</span>
        </div>
        <div>
          <p className="text-xs text-[#8A97B2] uppercase tracking-wider mb-1">Balance Due</p>
          <span className={`text-lg font-bold ${balanceDue > 0 ? "text-[#F87171]" : "text-[#22D38C]"}`}>
            {formatCurrency(balanceDue)}
          </span>
        </div>
        {overdueDays > 0 && (
          <div>
            <p className="text-xs text-[#8A97B2] uppercase tracking-wider mb-1">Overdue Days</p>
            <span className="text-[#F87171] font-semibold text-sm">{overdueDays} days</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-lg bg-[rgba(34,211,140,0.1)] border border-[#22D38C] px-4 py-3 text-sm text-[#22D38C]">
            Subscription updated successfully.
          </div>
        )}

        {/* Read-only display fields */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Member</label>
            <div className={readonlyClass}>{memberName || "—"}</div>
          </div>
          <div>
            <label className={labelClass}>Membership Plan</label>
            <div className={readonlyClass}>{membershipPlan || "—"}</div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className={labelClass}>Month</label>
            <div className={readonlyClass}>{month || "—"}</div>
          </div>
          <div>
            <label className={labelClass}>Tariff</label>
            <div className={readonlyClass}>{formatCurrency(tariff)}</div>
          </div>
          <div>
            <label className={labelClass}>Next Renewal</label>
            <div className={readonlyClass}>{nextRenewal || "—"}</div>
          </div>
        </div>

        <hr className="border-[#1E2D45]" />

        {/* Collected so far / dates — all derived from the invoice, not editable */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className={labelClass}>Collected</label>
            <div className={readonlyClass}>{formatCurrency(collected)}</div>
          </div>
          <div>
            <label className={labelClass}>Due Date</label>
            <div className={readonlyClass}>{due_date || "—"}</div>
          </div>
          <div>
            <label className={labelClass}>Paid Date</label>
            <div className={readonlyClass}>{paid_date || "—"}</div>
          </div>
        </div>

        <hr className="border-[#1E2D45]" />

        {/* Installment schedule — the same obligations the backend bills against */}
        {obligations.length > 1 && (
          <div className="rounded-lg border border-[#1E2D45] p-4 space-y-3">
            <h3 className="text-sm font-semibold text-[#E5EDF7]">Installments</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[#8FA3BF]">
                    <th className="py-1 pr-4 font-medium">#</th>
                    <th className="py-1 pr-4 font-medium">Due</th>
                    <th className="py-1 pr-4 font-medium text-right">Amount</th>
                    <th className="py-1 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {obligations.map((o) => {
                    const paid = o.outstanding <= 0;
                    const overdue =
                      !paid && !!o.due_date && new Date(o.due_date) < new Date();
                    return (
                      <tr key={o.idx} className="border-t border-[#1E2D45]">
                        <td className="py-2 pr-4 text-[#8FA3BF]">{o.idx}</td>
                        <td className="py-2 pr-4">{o.due_date ?? "—"}</td>
                        <td className="py-2 pr-4 text-right">
                          {formatCurrency(o.amount)}
                        </td>
                        <td className="py-2">
                          <span
                            className={
                              paid
                                ? "text-[#22D38C]"
                                : overdue
                                  ? "text-[#F87171]"
                                  : "text-[#8FA3BF]"
                            }
                          >
                            {paid ? "Paid" : overdue ? "Overdue" : "Due"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Record a payment — posts a real Payment Entry */}
        <div className="rounded-lg border border-[#1E2D45] p-4 space-y-4">
          <div className="flex items-baseline justify-between">
            <h3 className="text-sm font-semibold text-[#E5EDF7]">Record a Payment</h3>
            {balanceDue > 0 && (
              <span className="text-xs text-[#8FA3BF]">
                {formatCurrency(balanceDue)} outstanding
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className={labelClass}>Amount</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={payAmount}
                onChange={(e) => setPayAmount(e.target.value)}
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Payment Mode</label>
              <select
                value={payMode}
                onChange={(e) => setPayMode(e.target.value)}
                className={inputClass}
              >
                <option value="">Select mode…</option>
                {PAYMENT_MODES.map((pm) => (
                  <option key={pm} value={pm}>{pm}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>Payment Date</label>
              <input
                type="date"
                value={payDate}
                onChange={(e) => setPayDate(e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          {payError && (
            <div className="text-sm text-[#F87171]">{payError}</div>
          )}

          <button
            type="button"
            onClick={handleRecordPayment}
            disabled={paying || balanceDue <= 0 || !payAmount || !payDate}
            className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            {paying ? "Recording…" : "Record Payment"}
          </button>
        </div>

        <div>
          <label className={labelClass}>Comments</label>
          <textarea
            rows={3}
            value={comments}
            onChange={(e) => setComments(e.target.value)}
            placeholder="Optional notes…"
            className={`${inputClass} resize-none`}
          />
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-2 flex-wrap gap-3">
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
            >
              {submitting ? "Saving…" : "Save Changes"}
            </button>
            <a
              href="/subscriptions"
              className="px-5 py-2 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
            >
              Cancel
            </a>
          </div>

          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="border border-[#F87171] text-[#F87171] rounded-lg py-2 px-4 text-sm hover:bg-[rgba(248,113,113,0.1)] disabled:opacity-50 transition-colors"
          >
            {deleting ? "Deleting…" : "Delete Subscription"}
          </button>
        </div>
      </form>
    </div>
  );
}
