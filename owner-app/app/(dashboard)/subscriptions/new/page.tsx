"use client";

import { useState, useEffect, SyntheticEvent, Suspense } from "react";
import { extractFrappeError } from "@/lib/frappe";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";
import OfferPicker from "@/app/components/OfferPicker";
import PaymentTermsFields, {
  EMPTY_TERMS,
  describeGap,
  type TermsDraft,
} from "@/app/components/PaymentTermsFields";
import DiscountBox, {
  EMPTY_DISCOUNT,
  discountPayload,
  type DiscountDraft,
} from "@/app/components/DiscountBox";
import type { Capabilities, GapUnit, Member, MembershipPlan } from "@/lib/types";

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

/** Plan prices seen by the picker, so the discount preview knows the gross. */
const PLAN_AMOUNTS: Record<string, number> = {};

/** Each plan's own payment terms, so the form can show what the member gets by default. */
const PLAN_TERMS: Record<
  string,
  { parts: number; gap: number; unit: GapUnit | ""; rule: string }
> = {};

function planTermsSummary(plan: string): string {
  const t = PLAN_TERMS[plan];
  if (!t || t.parts < 2) return "Pays in full";
  const every = describeGap(t.gap, t.unit);
  return `Pays in ${t.parts} parts${every ? ` ${every}` : ""}`;
}

async function fetchPlans(q: string): Promise<LinkFieldOption[]> {
  const params = new URLSearchParams({ active_only: "1" });
  if (q) params.set("q", q);
  const res = await fetch(`/api/plans?${params.toString()}`);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: MembershipPlan[] };
  return (body.data ?? []).map((p) => {
    if (typeof p.amount === "number") PLAN_AMOUNTS[p.name] = p.amount;
    PLAN_TERMS[p.name] = {
      parts: Number(p.installment_count ?? 0),
      gap: Number(p.installment_gap_days ?? 0),
      unit: p.installment_gap_unit ?? "",
      rule: p.payment_due_rule ?? "",
    };
    return {
    id: p.name,
    label: p.plan_name,
    sub:
      p.amount !== undefined && p.duration_in_days
        ? `₹${p.amount} · ${p.duration_in_days} days`
        : undefined,
    };
  });
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];


const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

function NewSubscriptionForm() {
  const router = useRouter();
  // OP-2: "Convert to Member" lands here with ?member=…&member_label=… so the
  // desk goes straight from enquiry to enrolment without re-searching.
  const searchParams = useSearchParams();

  const [member, setMember] = useState(searchParams.get("member") ?? "");
  const [memberLabel, setMemberLabel] = useState(
    searchParams.get("member_label") ?? searchParams.get("member") ?? ""
  );
  const [membership_plan, setMembershipPlan] = useState("");
  const [planLabel, setPlanLabel] = useState("");
  const [month, setMonth] = useState("");
  // Per-member pricing: a plan holds ONE price, and a gym charges many. Blank
  // takes the plan's amount; typing a figure is this member's own rate.
  const [price, setPrice] = useState("");
  const [comments, setComments] = useState("");
  // WP-10: this member's own payment terms. Empty means "follow the plan".
  const [terms, setTerms] = useState<TermsDraft>(EMPTY_TERMS);
  // Stage 8 DS-1: a discount is granted here, with its cost shown before saving.
  const [discount, setDiscount] = useState<DiscountDraft>(EMPTY_DISCOUNT);
  // DS-2: an offer fills the discount in server-side when the membership is saved.
  const [offer, setOffer] = useState("");
  // DS-4: the plan's free trial applies unless this member is given a different one,
  // or none at all (they have already had theirs).
  const [trialDays, setTrialDays] = useState("");
  const [skipTrial, setSkipTrial] = useState(false);
  // DS-5: what this user may give away on their own, so the discount box can ask for
  // the owner's PIN at the right moment instead of after a refused save.
  const [caps, setCaps] = useState<Capabilities | null>(null);

  useEffect(() => {
    (async () => {
      const res = await fetch("/api/capabilities");
      if (!res.ok) return;
      const body = (await res.json()) as { message?: Capabilities };
      if (body.message) setCaps(body.message);
    })();
  }, []);


  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: Record<string, string | number | null> = {
      member,
      membership_plan,
      month,
      ...discountPayload(discount),
      offer: offer || null,
      skip_trial: skipTrial ? 1 : 0,
    };
    if (trialDays !== "" && Number.isFinite(Number(trialDays))) {
      payload.trial_days = Number(trialDays);
    }
    if (price !== "" && Number.isFinite(Number(price))) payload.tariff = Number(price);
    // Only send terms the owner actually changed; anything left alone stays on the plan.
    if (terms.payment_due_rule) payload.payment_due_rule = terms.payment_due_rule;
    if (terms.installment_count !== "") {
      payload.installment_count = Number(terms.installment_count);
    }
    if (terms.installment_gap_days !== "") {
      payload.installment_gap_days = Number(terms.installment_gap_days);
    }
    if (terms.installment_gap_unit !== "") {
      payload.installment_gap_unit = terms.installment_gap_unit;
    }
    if (comments) payload.comments = comments;

    try {
      const res = await fetch("/api/subscriptions", {
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

      const body = await res.json() as { data?: { name?: string } };
      const name = body?.data?.name;
      router.push(name ? `/subscriptions/${name}` : "/subscriptions");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/subscriptions" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Subscriptions
        </Link>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Add Subscription</h1>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}

        {/* Member */}
        <div>
          <label className={labelClass}>
            Member <span className="text-[#F87171]">*</span>
          </label>
          <LinkFieldPicker
            value={member}
            displayLabel={memberLabel}
            onChange={(id, label) => {
              setMember(id);
              setMemberLabel(label);
            }}
            fetchOptions={fetchMembers}
            placeholder="Search by name…"
            required
            emptyHint="No members found"
            inputClassName={inputClass}
          />
        </div>

        {/* Membership Plan */}
        <div>
          <label className={labelClass}>
            Membership Plan <span className="text-[#F87171]">*</span>
          </label>
          <LinkFieldPicker
            value={membership_plan}
            displayLabel={planLabel}
            onChange={(id, label) => {
              setMembershipPlan(id);
              setPlanLabel(label);
            }}
            fetchOptions={fetchPlans}
            placeholder="Search plans…"
            required
            emptyHint="No plans found"
            inputClassName={inputClass}
          />
        </div>

        {/* WP-10: how this member pays — in full, or in parts */}
        <PaymentTermsFields
          value={terms}
          onChange={setTerms}
          planSummary={membership_plan ? planTermsSummary(membership_plan) : "Pays in full"}
          inputClass={inputClass}
          labelClass={labelClass}
        />

        {/* Month + Price */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>
              Month <span className="text-[#F87171]">*</span>
            </label>
            <select
              required
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className={inputClass}
            >
              <option value="">Select month…</option>
              {MONTHS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Price</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="Leave blank to use the plan price"
              className={inputClass}
            />
          </div>
        </div>

        {/* WP-11: dates and status are all derived from the ERPNext Sales Invoice
            generated on enrolment. Money is recorded afterwards on the membership
            page ("Record a Payment"), which posts a Payment Entry. */}
        <div className="rounded-lg border border-[#1E2D45] bg-[#0F1B2D] p-4 text-sm text-[#8FA3BF]">
          Leave Price blank and this member pays the plan&rsquo;s rate; enter a figure and
          they pay that instead — the invoice follows whichever applies. On save the
          first invoice is raised automatically; record the payment from the
          membership page. A member with no price on either the membership or the
          plan is not billed at all, and appears on the &ldquo;cannot be billed&rdquo; list.
        </div>

        {/* Free trial */}
        <div className="rounded-lg border border-[#1E2D45] bg-[#0F1B2D] p-4 space-y-3">
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="text-sm font-semibold text-[#E6EDF7]">Free trial</h3>
            <span className="text-xs text-[#8A97B2]">Uses the plan&rsquo;s setting by default</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Trial days (override)</label>
              <input
                type="number"
                min="0"
                step="1"
                value={trialDays}
                onChange={(e) => setTrialDays(e.target.value)}
                placeholder="Plan's trial"
                disabled={skipTrial}
                className={inputClass}
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-[#E6EDF7] sm:pt-6">
              <input
                type="checkbox"
                checked={skipTrial}
                onChange={(e) => setSkipTrial(e.target.checked)}
                className="accent-[#22D38C]"
              />
              No free trial for this member
            </label>
          </div>
          <p className="text-xs text-[#8A97B2]">
            Nothing is invoiced while a trial runs. The first invoice is raised the day it
            ends, at the full rate — you don&rsquo;t have to do anything.
          </p>
        </div>

        <OfferPicker
          value={offer}
          onChange={setOffer}
          membershipPlan={membership_plan}
          member={member}
          inputClassName={inputClass}
          labelClassName={labelClass}
        />

        <DiscountBox
          value={discount}
          onChange={setDiscount}
          price={
            price !== "" && Number.isFinite(Number(price))
              ? Number(price)
              : PLAN_AMOUNTS[membership_plan]
          }
          member={member || undefined}
          capabilities={caps}
          inputClassName={inputClass}
          labelClassName={labelClass}
        />

        {/* Comments */}
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

        <p className="text-xs text-[#8A97B2]">
          Balance due, status, and next renewal are calculated automatically on save.
        </p>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            {submitting ? "Saving…" : "Save Subscription"}
          </button>
          <Link
            href="/subscriptions"
            className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}

export default function NewSubscriptionPage() {
  return (
    <Suspense fallback={null}>
      <NewSubscriptionForm />
    </Suspense>
  );
}
