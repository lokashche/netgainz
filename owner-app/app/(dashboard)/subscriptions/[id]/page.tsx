"use client";

import { useState, useEffect, SyntheticEvent, use } from "react";
import OfferPicker from "@/app/components/OfferPicker";
import Link from "next/link";
import LifecyclePanel from "@/app/components/LifecyclePanel";
import PaymentTermsPanel from "@/app/components/PaymentTermsPanel";
import DiscountBox, {
  EMPTY_DISCOUNT,
  discountPayload,
  type DiscountDraft,
} from "@/app/components/DiscountBox";
import { extractFrappeError } from "@/lib/frappe";
import { useRouter } from "next/navigation";
import type {
  AdvanceContext,
  Capabilities,
  Obligation,
  RefundContext,
  RefundResult,
  Subscription,
  SubscriptionStatus,
  WriteOffContext,
  DiscountLogRow,
} from "@/lib/types";

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
    case "Trial":
      // On a free trial: training, not yet billed.
      return `${base} bg-[rgba(94,234,212,0.15)] text-[#5EEAD4]`;
    case "Pending":
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    case "Overdue":
      return `${base} bg-[rgba(248,113,113,0.15)] text-[#F87171]`;
    case "Partial":
      return `${base} bg-[rgba(94,234,212,0.15)] text-[#5EEAD4]`;
    case "Cancelled":
      // OP-3: terminal — billing stopped, nothing renews.
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    case "Written Off":
      // Not "Paid": nobody paid. The receivable was given up as uncollectable.
      return `${base} bg-[rgba(251,191,36,0.15)] text-[#FBBF24]`;
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
  // Per-member pricing: `tariff` is what THIS member pays, not the plan's rate.
  // Editable, and it applies to the NEXT period — an issued invoice is never
  // rewritten behind the member's back.
  const [tariff, setTariff] = useState<string>("");
  const [nextRenewal, setNextRenewal] = useState("");

  // Derived from the membership's Sales Invoice — read-only (WP-11)
  const [collected, setCollected] = useState<number>(0);
  const [paid_date, setPaidDate] = useState("");
  const [due_date, setDueDate] = useState("");

  // Editable
  const [comments, setComments] = useState("");
  // Stage 8 DS-1: this member's negotiated discount, with its cost shown before saving.
  const [discount, setDiscount] = useState<DiscountDraft>(EMPTY_DISCOUNT);
  const [offer, setOffer] = useState("");
  // DS-4: read-only here — a trial is decided at enrolment and then runs its course.
  const [trialEndsOn, setTrialEndsOn] = useState<string>("");
  // DS-5: who changed this member's discount, when and why. Owner-only — the backend
  // refuses the read for anyone else, so the panel simply never appears for staff.
  const [discountHistory, setDiscountHistory] = useState<DiscountLogRow[]>([]);

  // Record-payment panel: posts a real Payment Entry (WP-11). Writing
  // fee_collected would record no revenue — Profit First and commissions read
  // collected cash from Payment Entries only.
  const [payAmount, setPayAmount] = useState("");
  const [payMode, setPayMode] = useState("");
  const [payDate, setPayDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [hasInvoice, setHasInvoice] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);
  // WP-8: a member may pay more than this period's invoice; the excess sits on
  // their account until a later invoice claims it.
  const [payAhead, setPayAhead] = useState(false);

  // WP-8 money-back panels. The backend guards both by role too — this only
  // hides what the signed-in user cannot do.
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [memberId, setMemberId] = useState("");
  const [advance, setAdvance] = useState<AdvanceContext | null>(null);
  const [advanceBusy, setAdvanceBusy] = useState(false);

  const [refundCtx, setRefundCtx] = useState<RefundContext | null>(null);
  const [refundAmount, setRefundAmount] = useState("");
  const [refundReason, setRefundReason] = useState("");
  const [refundDate, setRefundDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [refundCash, setRefundCash] = useState(true);
  const [refunding, setRefunding] = useState(false);
  const [refundError, setRefundError] = useState<string | null>(null);
  const [notices, setNotices] = useState<string[]>([]);

  const [writeOffCtx, setWriteOffCtx] = useState<WriteOffContext | null>(null);
  const [writeOffAmount, setWriteOffAmount] = useState("");
  const [writeOffReason, setWriteOffReason] = useState("");
  const [writingOff, setWritingOff] = useState(false);
  const [writeOffError, setWriteOffError] = useState<string | null>(null);

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
      setTariff(s.tariff === undefined || s.tariff === null ? "" : String(s.tariff));
      setOffer(s.offer ?? "");
      setTrialEndsOn(s.trial_ends_on ?? "");
      setDiscount({
        discount_type: s.discount_type ?? "",
        discount_value:
          s.discount_value === undefined || s.discount_value === null
            ? ""
            : String(s.discount_value),
        discount_duration: s.discount_duration ?? "First invoice only",
        discount_until: s.discount_until ?? "",
        discount_reason: s.discount_reason ?? "",
      });
      setNextRenewal(s.next_renewal ?? "");

      setMemberId(s.member ?? "");
      loadAdvances(s.member ?? "");
      setCollected((s.tariff ?? 0) - (s.balance_due ?? 0));
      setHasInvoice(Boolean(s.current_sales_invoice));
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

  async function loadDiscountHistory() {
    const res = await fetch(`/api/subscriptions/${encodeURIComponent(id)}/discount-history`);
    if (!res.ok) return;
    const body = (await res.json()) as { message?: DiscountLogRow[] };
    setDiscountHistory(body.message ?? []);
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

  async function loadMoneyPanels() {
    // Every one of these is supplementary: a failure must never blank the page.
    const [capsRes, refundRes, writeOffRes] = await Promise.all([
      fetch("/api/capabilities").catch(() => null),
      fetch(`/api/subscriptions/${encodeURIComponent(id)}/refund`).catch(() => null),
      fetch(`/api/subscriptions/${encodeURIComponent(id)}/write-off`).catch(() => null),
    ]);

    if (capsRes?.ok) {
      const body = (await capsRes.json()) as { message?: Capabilities };
      setCaps(body.message ?? null);
    }
    if (refundRes?.ok) {
      const body = (await refundRes.json()) as { message?: RefundContext };
      setRefundCtx(body.message ?? null);
      setRefundReason((prev) => prev || body.message?.reasons?.[0] || "");
    }
    if (writeOffRes?.ok) {
      const body = (await writeOffRes.json()) as { message?: WriteOffContext };
      setWriteOffCtx(body.message ?? null);
      setWriteOffAmount(String(body.message?.outstanding ?? ""));
      setWriteOffReason((prev) => prev || body.message?.reasons?.[0] || "");
    }
  }

  async function loadAdvances(member: string) {
    if (!member) return;
    try {
      const res = await fetch(`/api/members/${encodeURIComponent(member)}/advances`);
      if (!res.ok) return;
      const body = (await res.json()) as { message?: AdvanceContext };
      setAdvance(body.message ?? null);
    } catch {
      // supplementary
    }
  }

  async function reloadAll() {
    setLoading(true);
    await Promise.all([loadSub(), loadObligations(), loadMoneyPanels(), loadDiscountHistory()]);
  }

  useEffect(() => {
    (async () => {
      await Promise.all([loadSub(), loadObligations(), loadMoneyPanels(), loadDiscountHistory()]);
    })();
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
            allow_advance: payAhead,
          }),
        }
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setPayError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      // Re-fetch so the derived status / balance reflect the new Payment Entry.
      await reloadAll();
      await loadAdvances(memberId);
    } catch (err) {
      setPayError(err instanceof Error ? err.message : "Failed to record payment");
    } finally {
      setPaying(false);
    }
  }

  async function handleApplyAdvance() {
    setAdvanceBusy(true);
    setPayError(null);
    try {
      const res = await fetch(`/api/members/${encodeURIComponent(memberId)}/advances`, {
        method: "PUT",
      });
      const body = (await res.json().catch(() => ({}))) as {
        message?: { applied: number; warnings?: string[] };
      };
      if (!res.ok) {
        setPayError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      setNotices(body.message?.warnings ?? []);
      await reloadAll();
      await loadAdvances(memberId);
    } catch (err) {
      setPayError(err instanceof Error ? err.message : "Failed to apply money on account");
    } finally {
      setAdvanceBusy(false);
    }
  }

  async function handleRefund() {
    setRefunding(true);
    setRefundError(null);
    setNotices([]);
    const cash = refundCash && (refundCtx?.collected ?? 0) > 0;
    const verb = cash ? "Refund" : "Waive";
    if (!confirm(`${verb} ${formatCurrency(Number(refundAmount))} on this membership?`)) {
      setRefunding(false);
      return;
    }
    try {
      const res = await fetch(`/api/subscriptions/${encodeURIComponent(id)}/refund`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: Number(refundAmount),
          reason: refundReason,
          posting_date: refundDate,
          payment_mode: payMode || undefined,
          return_cash: refundCash,
        }),
      });
      const body = (await res.json().catch(() => ({}))) as { message?: RefundResult };
      if (!res.ok) {
        setRefundError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      setNotices(body.message?.warnings ?? []);
      setRefundAmount("");
      await reloadAll();
      await loadAdvances(memberId);
    } catch (err) {
      setRefundError(err instanceof Error ? err.message : "Failed to record the refund");
    } finally {
      setRefunding(false);
    }
  }

  async function handleWriteOff() {
    setWritingOff(true);
    setWriteOffError(null);
    if (
      !confirm(
        `Write off ${formatCurrency(Number(writeOffAmount))} as uncollectable? ` +
          "This records a loss — it does not collect anything."
      )
    ) {
      setWritingOff(false);
      return;
    }
    try {
      const res = await fetch(`/api/subscriptions/${encodeURIComponent(id)}/write-off`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: Number(writeOffAmount),
          reason: writeOffReason,
          posting_date: refundDate,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setWriteOffError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      await reloadAll();
    } catch (err) {
      setWriteOffError(err instanceof Error ? err.message : "Failed to write off the dues");
    } finally {
      setWritingOff(false);
    }
  }

  async function handleGenerateInvoice() {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/subscriptions/${encodeURIComponent(id)}/generate-invoice`,
        { method: "POST" }
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      await reloadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to raise the invoice");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(false);

    // WP-11: status / balance_due / due_date / next_renewal are all derived from
    // the Sales Invoice, and money is recorded as a Payment Entry. What the owner
    // still sets by hand is the note and this member's own price.
    const payload: Record<string, string | number | null> = {
      comments,
      ...discountPayload(discount),
      offer: offer || null,
    };
    if (tariff !== "" && Number.isFinite(Number(tariff))) payload.tariff = Number(tariff);

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
        <Link href="/subscriptions" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Subscriptions
        </Link>
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
        {(refundCtx?.credited ?? 0) > 0 && (
          <div>
            <p className="text-xs text-[#8A97B2] uppercase tracking-wider mb-1">Refunded</p>
            <span className="text-[#5EEAD4] font-semibold text-sm">
              {formatCurrency(refundCtx?.credited)}
            </span>
          </div>
        )}
        {(writeOffCtx?.written_off ?? 0) > 0 && (
          <div>
            <p className="text-xs text-[#8A97B2] uppercase tracking-wider mb-1">Written Off</p>
            <span className="text-[#FBBF24] font-semibold text-sm">
              {formatCurrency(writeOffCtx?.written_off)}
            </span>
          </div>
        )}
        {(advance?.balance ?? 0) > 0 && (
          <div>
            <p className="text-xs text-[#8A97B2] uppercase tracking-wider mb-1">On Account</p>
            <span className="text-[#22D38C] font-semibold text-sm">
              {formatCurrency(advance?.balance)}
            </span>
          </div>
        )}
      </div>

      {notices.length > 0 && (
        <div className="rounded-lg bg-[rgba(251,191,36,0.08)] border border-[#FBBF24] px-4 py-3 mb-6 text-sm text-[#FBBF24] space-y-1">
          {notices.map((n) => (
            <p key={n}>{n}</p>
          ))}
        </div>
      )}

      {/* No invoice means no price could be resolved — the member is enrolled but
          not being billed. Deliberate: a submitted Rs.0 invoice is silent revenue
          leakage and a mess to unwind. */}
      {!hasInvoice && (
        <div className="rounded-lg bg-[rgba(251,191,36,0.08)] border border-[#FBBF24] px-4 py-3 mb-6 text-sm text-[#FBBF24]">
          <p className="font-semibold">This member is not being billed.</p>
          <p className="mt-1">
            No price is set on the membership and the plan has no amount either, so no
            invoice is raised. Enter a Price below, save, then raise the first invoice.
          </p>
          <button
            type="button"
            onClick={handleGenerateInvoice}
            disabled={generating}
            className="mt-3 border border-[#FBBF24] text-[#FBBF24] rounded-lg py-1.5 px-4 text-sm hover:bg-[rgba(251,191,36,0.12)] disabled:opacity-50 transition-colors"
          >
            {generating ? "Raising…" : "Raise the first invoice"}
          </button>
        </div>
      )}

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
            <label className={labelClass}>Price</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={tariff}
              onChange={(e) => setTariff(e.target.value)}
              placeholder="Plan price"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Next Renewal</label>
            <div className={readonlyClass}>{nextRenewal || "—"}</div>
          </div>
        </div>

        {trialEndsOn && (
          <div className="rounded-lg border border-[#5EEAD4] bg-[rgba(94,234,212,0.08)] p-4 text-sm text-[#8FA3BF]">
            Free trial until <span className="text-[#E6EDF7]">{trialEndsOn}</span>. Nothing is
            invoiced while it runs — the first invoice is raised the next day, at the full
            rate, automatically.
          </div>
        )}

        <OfferPicker
          value={offer}
          onChange={setOffer}
          membershipPlan={membershipPlan}
          member={memberId || undefined}
          inputClassName={inputClass}
          labelClassName={labelClass}
        />

        <DiscountBox
          value={discount}
          onChange={setDiscount}
          price={tariff !== "" && Number.isFinite(Number(tariff)) ? Number(tariff) : undefined}
          membership={subName || undefined}
          member={memberId || undefined}
          capabilities={caps}
          inputClassName={inputClass}
          labelClassName={labelClass}
        />

        <p className="text-xs text-[#8A97B2]">
          A changed discount applies to the NEXT invoice — one already raised keeps the
          figures it was billed at.
        </p>

        {discountHistory.length > 0 && (
          <div className="rounded-lg border border-[#1E2D45] bg-[#0F1B2D] p-4">
            <h3 className="text-sm font-semibold text-[#E6EDF7] mb-2">Discount history</h3>
            <ul className="space-y-2 text-sm text-[#8FA3BF]">
              {discountHistory.map((h) => (
                <li key={h.name} className="flex flex-wrap gap-x-2">
                  <span className="text-[#E6EDF7]">{h.action}</span>
                  <span>
                    {h.action === "Removed"
                      ? `${h.previous_type ?? ""} ${h.previous_value ?? ""}`.trim()
                      : `${h.discount_type ?? ""} ${h.discount_value ?? ""}`.trim()}
                    {h.action === "Changed" && h.previous_value !== undefined
                      ? ` (was ${h.previous_value})`
                      : ""}
                  </span>
                  {h.offer && <span className="text-[#5EEAD4]">via {h.offer}</span>}
                  {h.approved === 1 && <span className="text-[#FBBF24]">owner-approved</span>}
                  <span className="text-[#8A97B2]">
                    · {h.granted_by ?? "—"} · {h.creation?.slice(0, 16)}
                  </span>
                  {h.reason && <span className="w-full text-xs text-[#8A97B2]">{h.reason}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

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

        {/* WP-10: this member's own payment terms, changeable after they joined */}
        <PaymentTermsPanel
          membershipId={id}
          inputClass={inputClass}
          labelClass={labelClass}
        />

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

          {/* Paying ahead: the excess is parked on the member's account and is
              claimed by the next period's invoice. It is not revenue until then. */}
          <label className="flex items-center gap-2 text-sm text-[#8FA3BF]">
            <input
              type="checkbox"
              checked={payAhead}
              onChange={(e) => setPayAhead(e.target.checked)}
              className="accent-[#22D38C]"
            />
            Member is paying ahead — keep anything over the balance on their account
          </label>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleRecordPayment}
              disabled={paying || (balanceDue <= 0 && !payAhead) || !payAmount || !payDate}
              className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
            >
              {paying ? "Recording…" : "Record Payment"}
            </button>

            {(advance?.balance ?? 0) > 0 && (
              <button
                type="button"
                onClick={handleApplyAdvance}
                disabled={advanceBusy || balanceDue <= 0}
                className="border border-[#22D38C] text-[#22D38C] rounded-lg py-2 px-4 text-sm hover:bg-[rgba(34,211,140,0.1)] disabled:opacity-50 transition-colors"
              >
                {advanceBusy
                  ? "Applying…"
                  : `Apply ${formatCurrency(advance?.balance)} on account`}
              </button>
            )}
          </div>

          {(advance?.advances?.length ?? 0) > 0 && (
            <p className="text-xs text-[#8FA3BF]">
              On account:{" "}
              {advance?.advances
                .map((a) => `${formatCurrency(a.unapplied)} taken ${a.posting_date}`)
                .join(" · ")}
              . It counts as revenue on the day it was received, once applied.
            </p>
          )}
        </div>

        {/* Give money back — a credit note, plus the cash when there is any to
            return. Owner-only; the backend enforces that too. */}
        {caps?.can_refund && refundCtx?.sales_invoice && (
          <div className="rounded-lg border border-[#1E2D45] p-4 space-y-4">
            <div className="flex items-baseline justify-between">
              <h3 className="text-sm font-semibold text-[#E5EDF7]">Refund or Waive</h3>
              <span className="text-xs text-[#8FA3BF]">
                {formatCurrency(refundCtx.refundable)} still creditable
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className={labelClass}>Amount</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={refundAmount}
                  onChange={(e) => setRefundAmount(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Reason</label>
                <select
                  value={refundReason}
                  onChange={(e) => setRefundReason(e.target.value)}
                  className={inputClass}
                >
                  {refundCtx.reasons.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelClass}>Date</label>
                <input
                  type="date"
                  value={refundDate}
                  onChange={(e) => setRefundDate(e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm text-[#8FA3BF]">
              <input
                type="checkbox"
                checked={refundCash}
                onChange={(e) => setRefundCash(e.target.checked)}
                className="accent-[#22D38C]"
              />
              Hand the cash back (leave off to only cancel the charge)
            </label>
            <p className="text-xs text-[#8FA3BF]">
              {refundCtx.collected > 0
                ? "Money that leaves the bank also leaves your Profit First figures for that date."
                : "Nothing has been collected on this invoice, so this only cancels the charge — no cash moves."}
            </p>

            {refundError && <div className="text-sm text-[#F87171]">{refundError}</div>}

            <button
              type="button"
              onClick={handleRefund}
              disabled={
                refunding ||
                !refundAmount ||
                Number(refundAmount) <= 0 ||
                refundCtx.refundable <= 0
              }
              className="border border-[#5EEAD4] text-[#5EEAD4] rounded-lg py-2 px-5 text-sm hover:bg-[rgba(94,234,212,0.1)] disabled:opacity-50 transition-colors"
            >
              {refunding ? "Recording…" : "Record Refund"}
            </button>
          </div>
        )}

        {/* Give up on dues that will never arrive. A loss, not a collection. */}
        {caps?.can_write_off && (writeOffCtx?.outstanding ?? 0) > 0 && (
          <div className="rounded-lg border border-[#1E2D45] p-4 space-y-4">
            <div className="flex items-baseline justify-between">
              <h3 className="text-sm font-semibold text-[#E5EDF7]">Write Off Uncollectable Dues</h3>
              <span className="text-xs text-[#8FA3BF]">
                {formatCurrency(writeOffCtx?.outstanding)} outstanding
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Amount</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={writeOffAmount}
                  onChange={(e) => setWriteOffAmount(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Reason</label>
                <select
                  value={writeOffReason}
                  onChange={(e) => setWriteOffReason(e.target.value)}
                  className={inputClass}
                >
                  {(writeOffCtx?.reasons ?? []).map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            </div>

            <p className="text-xs text-[#8FA3BF]">
              Books the balance as a bad-debt expense and stops chasing it. No money
              is collected, so your Profit First figures do not change.
            </p>

            {writeOffError && <div className="text-sm text-[#F87171]">{writeOffError}</div>}

            <button
              type="button"
              onClick={handleWriteOff}
              disabled={writingOff || !writeOffAmount || Number(writeOffAmount) <= 0}
              className="border border-[#FBBF24] text-[#FBBF24] rounded-lg py-2 px-5 text-sm hover:bg-[rgba(251,191,36,0.1)] disabled:opacity-50 transition-colors"
            >
              {writingOff ? "Writing off…" : "Write Off"}
            </button>
          </div>
        )}

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
            <Link
              href="/subscriptions"
              className="px-5 py-2 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
            >
              Cancel
            </Link>
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

      {/* OP-3: freeze / change plan / cancel / transfer */}
      <LifecyclePanel
        membershipId={id}
        status={subStatus}
        currentPlan={membershipPlan}
        onChanged={reloadAll}
      />
    </div>
  );
}
