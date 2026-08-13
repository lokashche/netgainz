"use client";

import { useEffect, useState, SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";
import type { MembershipPlan, Offer, OfferDuration } from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const DURATIONS: { value: OfferDuration; hint: string }[] = [
  { value: "First invoice only", hint: "A joining offer — the next invoice bills the full rate." },
  { value: "Every invoice", hint: "A rate the member keeps for as long as they stay." },
  { value: "Until the offer ends", hint: "The discount stops on the offer's end date." },
];

export type OfferFormValues = {
  offer_name: string;
  description: string;
  discount_type: "Percentage" | "Amount";
  discount_value: string;
  discount_duration: OfferDuration;
  valid_from: string;
  valid_upto: string;
  max_total_uses: string;
  coupon_code: string;
  max_uses_per_member: string;
  plans: string[];
};

export function toFormValues(offer?: Offer): OfferFormValues {
  return {
    offer_name: offer?.offer_name ?? "",
    description: offer?.description ?? "",
    discount_type: offer?.discount_type ?? "Percentage",
    discount_value: offer?.discount_value === undefined ? "" : String(offer.discount_value),
    discount_duration: offer?.discount_duration ?? "First invoice only",
    valid_from: offer?.valid_from ?? new Date().toISOString().slice(0, 10),
    valid_upto: offer?.valid_upto ?? "",
    max_total_uses: offer?.max_total_uses ? String(offer.max_total_uses) : "",
    coupon_code: offer?.coupon_code ?? "",
    max_uses_per_member: offer?.max_uses_per_member ? String(offer.max_uses_per_member) : "",
    plans: (offer?.plans ?? []).map((p) => p.membership_plan),
  };
}

interface OfferFormProps {
  /** Absent = creating a new offer. */
  offerName?: string;
  initial: OfferFormValues;
  /** Shown above the buttons on an existing offer (usage, end-now, …). */
  children?: React.ReactNode;
}

/**
 * DS-2: the whole campaign in gym words — what comes off, who it applies to, when it
 * runs, and how many members may have it. Everything it means for an invoice is
 * decided on the server when the offer is given to a member.
 */
export default function OfferForm({ offerName, initial, children }: OfferFormProps) {
  const router = useRouter();
  const [values, setValues] = useState<OfferFormValues>(initial);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const res = await fetch("/api/plans?active_only=1");
      if (!res.ok) return;
      const body = (await res.json()) as { data?: MembershipPlan[] };
      setPlans(body.data ?? []);
    })();
  }, []);

  const set = (patch: Partial<OfferFormValues>) => setValues({ ...values, ...patch });

  function togglePlan(plan: string) {
    set({
      plans: values.plans.includes(plan)
        ? values.plans.filter((p) => p !== plan)
        : [...values.plans, plan],
    });
  }

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSaved(false);

    const payload = {
      offer_name: values.offer_name,
      description: values.description,
      discount_type: values.discount_type,
      discount_value: Number(values.discount_value) || 0,
      discount_duration: values.discount_duration,
      valid_from: values.valid_from,
      valid_upto: values.valid_upto || null,
      max_total_uses: Number(values.max_total_uses) || 0,
      coupon_code: values.coupon_code,
      max_uses_per_member: Number(values.max_uses_per_member) || 0,
      plans: values.plans.map((p) => ({ membership_plan: p })),
    };

    try {
      const res = await fetch(
        offerName ? `/api/offers/${encodeURIComponent(offerName)}` : "/api/offers",
        {
          method: offerName ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setSubmitting(false);
        return;
      }
      const body = (await res.json()) as { data?: { name?: string } };
      if (offerName) {
        setSaved(true);
        setSubmitting(false);
        setTimeout(() => setSaved(false), 3000);
        router.refresh();
      } else {
        router.push(body?.data?.name ? `/offers/${encodeURIComponent(body.data.name)}` : "/offers");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setSubmitting(false);
    }
  }

  const durationHint = DURATIONS.find((d) => d.value === values.discount_duration)?.hint;

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5"
    >
      {error && (
        <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
          {error}
        </div>
      )}
      {saved && (
        <div className="rounded-lg bg-[rgba(34,211,140,0.1)] border border-[#22D38C] px-4 py-3 text-sm text-[#22D38C]">
          Saved. Members already on this offer keep the rate they were given.
        </div>
      )}

      <div>
        <label className={labelClass}>
          Offer Name <span className="text-[#F87171]">*</span>
        </label>
        <input
          required
          value={values.offer_name}
          onChange={(e) => set({ offer_name: e.target.value })}
          placeholder="New Year 20%"
          className={inputClass}
          disabled={Boolean(offerName)}
        />
        {offerName && (
          <p className="mt-1 text-xs text-[#8A97B2]">
            The name is how memberships refer to this offer, so it cannot be changed here.
          </p>
        )}
      </div>

      <div>
        <label className={labelClass}>Description</label>
        <textarea
          rows={2}
          value={values.description}
          onChange={(e) => set({ description: e.target.value })}
          placeholder="What the member is told — for whoever is at the desk."
          className={`${inputClass} resize-none`}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>
            Discount <span className="text-[#F87171]">*</span>
          </label>
          <select
            value={values.discount_type}
            onChange={(e) =>
              set({ discount_type: e.target.value as OfferFormValues["discount_type"] })
            }
            className={inputClass}
          >
            <option value="Percentage">Percentage off (%)</option>
            <option value="Amount">Amount off (₹)</option>
          </select>
        </div>
        <div>
          <label className={labelClass}>
            {values.discount_type === "Percentage" ? "Percent off" : "Amount off"}{" "}
            <span className="text-[#F87171]">*</span>
          </label>
          <input
            required
            type="number"
            min="0"
            max={values.discount_type === "Percentage" ? "100" : undefined}
            step={values.discount_type === "Percentage" ? "1" : "0.01"}
            value={values.discount_value}
            onChange={(e) => set({ discount_value: e.target.value })}
            placeholder={values.discount_type === "Percentage" ? "20" : "1000"}
            className={inputClass}
          />
        </div>
      </div>

      <div>
        <label className={labelClass}>
          Applies to <span className="text-[#F87171]">*</span>
        </label>
        <select
          value={values.discount_duration}
          onChange={(e) => set({ discount_duration: e.target.value as OfferDuration })}
          className={inputClass}
        >
          {DURATIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.value}
            </option>
          ))}
        </select>
        {durationHint && <p className="mt-1 text-xs text-[#8A97B2]">{durationHint}</p>}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className={labelClass}>
            Runs from <span className="text-[#F87171]">*</span>
          </label>
          <input
            required
            type="date"
            value={values.valid_from}
            onChange={(e) => set({ valid_from: e.target.value })}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Runs until</label>
          <input
            type="date"
            value={values.valid_upto}
            onChange={(e) => set({ valid_upto: e.target.value })}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Limit</label>
          <input
            type="number"
            min="0"
            step="1"
            value={values.max_total_uses}
            onChange={(e) => set({ max_total_uses: e.target.value })}
            placeholder="No limit"
            className={inputClass}
          />
          <p className="mt-1 text-xs text-[#8A97B2]">e.g. 50 for &ldquo;first 50 members&rdquo;.</p>
        </div>
      </div>

      <div>
        <label className={labelClass}>Plans</label>
        <div className="rounded-lg border border-[#1E2D45] bg-[#0F1B2D] p-3 space-y-2">
          {plans.length === 0 ? (
            <p className="text-sm text-[#8A97B2]">No active plans yet.</p>
          ) : (
            plans.map((plan) => (
              <label key={plan.name} className="flex items-center gap-2 text-sm text-[#E6EDF7]">
                <input
                  type="checkbox"
                  checked={values.plans.includes(plan.name)}
                  onChange={() => togglePlan(plan.name)}
                  className="accent-[#22D38C]"
                />
                {plan.plan_name}
              </label>
            ))
          )}
          <p className="text-xs text-[#8A97B2] pt-1">
            Tick none to run the offer on every plan.
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-[#1E2D45] bg-[#0F1B2D] p-4 space-y-4">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-semibold text-[#E6EDF7]">Coupon code</h3>
          <span className="text-xs text-[#8A97B2]">Optional</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Code</label>
            <input
              value={values.coupon_code}
              onChange={(e) => set({ coupon_code: e.target.value })}
              placeholder="FIT50"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Limit per member</label>
            <input
              type="number"
              min="0"
              step="1"
              value={values.max_uses_per_member}
              onChange={(e) => set({ max_uses_per_member: e.target.value })}
              placeholder="No limit"
              className={inputClass}
            />
          </div>
        </div>
        <p className="text-xs text-[#8A97B2]">
          Give the offer a code and it stops appearing in the list at enrolment — a member
          has to quote the code to get it. Capitals and spaces do not matter.
        </p>
      </div>

      {children}

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={submitting}
          className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
        >
          {submitting ? "Saving…" : offerName ? "Save Offer" : "Create Offer"}
        </button>
        <a
          href="/offers"
          className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
        >
          Cancel
        </a>
      </div>
    </form>
  );
}
