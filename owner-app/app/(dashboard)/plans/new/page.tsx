"use client";

import { useState, SyntheticEvent } from "react";
import { extractFrappeError } from "@/lib/frappe";
import { useRouter } from "next/navigation";
import { GAP_UNITS } from "@/app/components/PaymentTermsFields";
import { PLAN_TYPE_DAYS } from "@/lib/plans";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function NewPlanPage() {
  const router = useRouter();

  const [plan_name, setPlanName] = useState("");
  const [duration_in_days, setDuration] = useState("");
  const [plan_type, setPlanType] = useState("Monthly");
  const [billing_mode, setBillingMode] = useState("Commitment");
  const [payment_due_rule, setPaymentDueRule] = useState("On joining");
  const [installment_count, setInstallmentCount] = useState("1");
  const [installment_gap_days, setInstallmentGapDays] = useState("30");
  const [installment_gap_unit, setInstallmentGapUnit] = useState("Days");
  const [trial_days, setTrialDays] = useState("0");

  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [is_active, setIsActive] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: Record<string, string | number> = {
      plan_name,
      is_active: is_active ? 1 : 0,
    };
    payload.plan_type = plan_type;
    payload.billing_mode = billing_mode;
    payload.payment_due_rule = payment_due_rule;
    payload.installment_count = Number(installment_count);
    payload.installment_gap_days = Number(installment_gap_days);
    payload.installment_gap_unit = installment_gap_unit;
    payload.trial_days = Number(trial_days) || 0;
    if (duration_in_days) payload.duration_in_days = Number(duration_in_days);
    if (amount) payload.amount = Number(amount);
    if (description) payload.description = description;

    try {
      const res = await fetch("/api/plans", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setSubmitting(false);
        return;
      }

      router.push("/plans");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/plans" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Plans
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Add Membership Plan</h1>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}

        {/* Plan Name */}
        <div>
          <label className={labelClass}>
            Plan Name <span className="text-[#F87171]">*</span>
          </label>
          <input
            type="text"
            required
            value={plan_name}
            onChange={(e) => setPlanName(e.target.value)}
            placeholder="e.g. Basic 30 Day"
            className={inputClass}
          />
        </div>

        {/* Cadence + Billing mode (WP-10) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Plan Type</label>
            <select
              value={plan_type}
              onChange={(e) => setPlanType(e.target.value)}
              className={inputClass}
            >
              {["Monthly", "Quarterly", "Half-Yearly", "Yearly", "Custom"].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Billing Mode</label>
            <select
              value={billing_mode}
              onChange={(e) => setBillingMode(e.target.value)}
              className={inputClass}
            >
              <option value="Commitment">One invoice for the period</option>
              <option value="Pay-as-you-go">A separate invoice each installment</option>
            </select>
          </div>
        </div>

        {/* Payment policy — becomes the ERPNext payment terms behind the scenes */}
        <div className="rounded-lg border border-[#1E2D45] p-4 space-y-4">
          <h3 className="text-sm font-semibold text-[#E5EDF7]">Payment Policy</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className={labelClass}>Payment Due</label>
              <select
                value={payment_due_rule}
                onChange={(e) => setPaymentDueRule(e.target.value)}
                className={inputClass}
              >
                {["On joining", "Within 7 days", "By the 5th of next month"].map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>Allow Installments</label>
              <select
                value={installment_count}
                onChange={(e) => setInstallmentCount(e.target.value)}
                className={inputClass}
              >
                <option value="1">Pay in full</option>
                {[2, 3, 4, 6, 12].map((n) => (
                  <option key={n} value={String(n)}>{n} parts</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>Collect Each Part Every</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  min="1"
                  value={installment_gap_days}
                  onChange={(e) => setInstallmentGapDays(e.target.value)}
                  disabled={installment_count === "1"}
                  className={`${inputClass} disabled:opacity-50 w-20 shrink-0`}
                />
                <select
                  aria-label="Unit"
                  value={installment_gap_unit}
                  onChange={(e) => setInstallmentGapUnit(e.target.value)}
                  disabled={installment_count === "1"}
                  className={`${inputClass} disabled:opacity-50`}
                >
                  {GAP_UNITS.map((u) => (
                    <option key={u.value} value={u.value}>{u.label}</option>
                  ))}
                </select>
              </div>
              <p className="text-xs text-[#8A97B2] mt-1">
                {billing_mode === "Pay-as-you-go"
                  ? "Not used on this billing mode — each part is its own invoice on its own cycle."
                  : "Months means the same day next month, so nothing drifts."}
              </p>
            </div>
          </div>
        </div>

        {/* Free trial — DS-4. Nothing is invoiced until it ends. */}
        <div className="rounded-lg border border-[#1E2D45] p-4 space-y-3">
          <h3 className="text-sm font-semibold text-[#E5EDF7]">Free Trial</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Trial Days</label>
              <input
                type="number"
                min="0"
                step="1"
                value={trial_days}
                onChange={(e) => setTrialDays(e.target.value)}
                className={inputClass}
              />
            </div>
          </div>
          <p className="text-xs text-[#8A97B2]">
            0 = no trial. A new member on this plan trains free for this many days; their
            first invoice is raised the day the trial ends, at the full rate, automatically.
          </p>
        </div>

        {/* Duration + Amount */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Duration (Days)</label>
            <input
              type="number"
              min="1"
              value={
                plan_type !== "Custom"
                  ? String(PLAN_TYPE_DAYS[plan_type] ?? "")
                  : duration_in_days
              }
              onChange={(e) => setDuration(e.target.value)}
              placeholder="e.g. 30"
              disabled={plan_type !== "Custom"}
              className={`${inputClass} disabled:opacity-75`}
            />
          </div>
          <div>
            <label className={labelClass}>Amount</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="e.g. 1500"
              className={inputClass}
            />
          </div>
        </div>

        {/* Description */}
        <div>
          <label className={labelClass}>Description</label>
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description…"
            className={`${inputClass} resize-none`}
          />
        </div>

        {/* Is Active */}
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="is_active"
            checked={is_active}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 rounded border-[#1E2D45] bg-[#1A2540] accent-[#22D38C]"
          />
          <label htmlFor="is_active" className="text-sm text-[#E6EDF7] cursor-pointer">
            Active
          </label>
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            {submitting ? "Saving…" : "Save Plan"}
          </button>
          <a
            href="/plans"
            className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
          >
            Cancel
          </a>
        </div>
      </form>
    </div>
  );
}
