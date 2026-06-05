"use client";

import { useState, useEffect, SyntheticEvent, use } from "react";
import { extractFrappeError } from "@/lib/frappe";
import { useRouter } from "next/navigation";
import type { Subscription, SubscriptionStatus } from "@/lib/types";

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

  // Editable fields
  const [fee_collected, setFeeCollected] = useState("");
  const [payment_mode, setPaymentMode] = useState("");
  const [paid_date, setPaidDate] = useState("");
  const [due_date, setDueDate] = useState("");
  const [comments, setComments] = useState("");

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

      setFeeCollected(s.fee_collected !== undefined ? String(s.fee_collected) : "0");
      setPaymentMode(s.payment_mode ?? "");
      setPaidDate(s.paid_date ?? "");
      setDueDate(s.due_date ?? "");
      setComments(s.comments ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load subscription");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSub();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(false);

    const payload: Record<string, string | number> = {
      fee_collected: Number(fee_collected),
    };
    payload.payment_mode = payment_mode;
    payload.paid_date = paid_date;
    payload.due_date = due_date;
    payload.comments = comments;

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

        {/* Editable fields */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Fee Collected</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={fee_collected}
              onChange={(e) => setFeeCollected(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Payment Mode</label>
            <select
              value={payment_mode}
              onChange={(e) => setPaymentMode(e.target.value)}
              className={inputClass}
            >
              <option value="">Select mode…</option>
              {PAYMENT_MODES.map((pm) => (
                <option key={pm} value={pm}>{pm}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Due Date</label>
            <input
              type="date"
              value={due_date}
              onChange={(e) => setDueDate(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Paid Date</label>
            <input
              type="date"
              value={paid_date}
              onChange={(e) => setPaidDate(e.target.value)}
              className={inputClass}
            />
          </div>
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
