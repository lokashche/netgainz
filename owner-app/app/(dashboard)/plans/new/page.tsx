"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function NewPlanPage() {
  const router = useRouter();

  const [plan_name, setPlanName] = useState("");
  const [duration_in_days, setDuration] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [is_active, setIsActive] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: Record<string, string | number> = {
      plan_name,
      is_active: is_active ? 1 : 0,
    };
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
        const body = await res.json().catch(() => ({})) as { message?: string; _error_message?: string };
        setError(body._error_message ?? body.message ?? `Error ${res.status}`);
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

        {/* Duration + Amount */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Duration (Days)</label>
            <input
              type="number"
              min="1"
              value={duration_in_days}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="e.g. 30"
              className={inputClass}
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
