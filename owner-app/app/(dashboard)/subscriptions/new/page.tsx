"use client";

import { useState, SyntheticEvent } from "react";
import { extractFrappeError } from "@/lib/frappe";
import { useRouter } from "next/navigation";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";
import type { Member, MembershipPlan } from "@/lib/types";

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

async function fetchPlans(q: string): Promise<LinkFieldOption[]> {
  const params = new URLSearchParams({ active_only: "1" });
  if (q) params.set("q", q);
  const res = await fetch(`/api/plans?${params.toString()}`);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: MembershipPlan[] };
  return (body.data ?? []).map((p) => ({
    id: p.name,
    label: p.plan_name,
    sub:
      p.amount !== undefined && p.duration_in_days
        ? `₹${p.amount} · ${p.duration_in_days} days`
        : undefined,
  }));
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const PAYMENT_MODES = ["Cash", "UPI", "Card", "Bank Transfer", "Online"];

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function NewSubscriptionPage() {
  const router = useRouter();

  const [member, setMember] = useState("");
  const [memberLabel, setMemberLabel] = useState("");
  const [membership_plan, setMembershipPlan] = useState("");
  const [planLabel, setPlanLabel] = useState("");
  const [month, setMonth] = useState("");
  const [tariff, setTariff] = useState("");
  const [fee_collected, setFeeCollected] = useState("0");
  const [payment_mode, setPaymentMode] = useState("");
  const [due_date, setDueDate] = useState("");
  const [paid_date, setPaidDate] = useState("");
  const [comments, setComments] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: Record<string, string | number> = {
      member,
      membership_plan,
      month,
      tariff: Number(tariff),
      fee_collected: Number(fee_collected),
    };
    if (payment_mode) payload.payment_mode = payment_mode;
    if (due_date) payload.due_date = due_date;
    if (paid_date) payload.paid_date = paid_date;
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
        <a href="/subscriptions" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Subscriptions
        </a>
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

        {/* Month + Payment Mode */}
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

        {/* Tariff + Fee Collected */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>
              Tariff / Fee Amount <span className="text-[#F87171]">*</span>
            </label>
            <input
              type="number"
              required
              min="0"
              step="0.01"
              value={tariff}
              onChange={(e) => setTariff(e.target.value)}
              placeholder="e.g. 1500"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Fee Collected</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={fee_collected}
              onChange={(e) => setFeeCollected(e.target.value)}
              placeholder="0"
              className={inputClass}
            />
          </div>
        </div>

        {/* Due Date + Paid Date */}
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
          <a
            href="/subscriptions"
            className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
          >
            Cancel
          </a>
        </div>
      </form>
    </div>
  );
}
