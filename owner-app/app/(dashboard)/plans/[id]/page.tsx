"use client";

import { useState, useEffect, FormEvent, use } from "react";
import { useRouter } from "next/navigation";
import type { MembershipPlan } from "@/lib/types";

type Params = Promise<{ id: string }>;

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function PlanDetailPage({ params }: { params: Params }) {
  const { id } = use(params);
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [plan_name, setPlanName] = useState("");
  const [duration_in_days, setDuration] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [is_active, setIsActive] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/plans/${encodeURIComponent(id)}`);
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const body = await res.json() as { data?: MembershipPlan };
        const p = body.data;
        if (!p) throw new Error("Plan not found");
        setPlanName(p.plan_name ?? "");
        setDuration(p.duration_in_days !== undefined ? String(p.duration_in_days) : "");
        setAmount(p.amount !== undefined ? String(p.amount) : "");
        setDescription(p.description ?? "");
        setIsActive(p.is_active === 1);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load plan");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(false);

    const payload: Record<string, string | number> = {
      plan_name,
      is_active: is_active ? 1 : 0,
    };
    if (duration_in_days) payload.duration_in_days = Number(duration_in_days);
    if (amount) payload.amount = Number(amount);
    payload.description = description;

    try {
      const res = await fetch(`/api/plans/${encodeURIComponent(id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { message?: string; _error_message?: string };
        setError(body._error_message ?? body.message ?? `Error ${res.status}`);
      } else {
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete plan "${id}"? This cannot be undone.`)) return;
    setDeleting(true);
    setError(null);

    try {
      const res = await fetch(`/api/plans/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { message?: string; _error_message?: string };
        setError(body._error_message ?? body.message ?? `Error ${res.status}`);
        setDeleting(false);
        return;
      }

      router.push("/plans");
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
        <a href="/plans" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Plans
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">
          <span className="font-mono text-[#5EEAD4] text-lg bg-[#1A2540] px-2 py-0.5 rounded-md">
            {id}
          </span>
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-lg bg-[rgba(34,211,140,0.1)] border border-[#22D38C] px-4 py-3 text-sm text-[#22D38C]">
            Plan updated successfully.
          </div>
        )}

        {/* Plan Name — read-only heading, it IS the document ID */}
        <div>
          <label className={labelClass}>Plan Name</label>
          <p className="text-sm text-[#E6EDF7] bg-[#1A2540] border border-[#1E2D45] rounded-lg px-3 py-2.5">
            {plan_name || id}
          </p>
          <p className="text-xs text-[#8A97B2] mt-1">Plan name is the document ID and cannot be changed.</p>
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
              href="/plans"
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
            {deleting ? "Deleting…" : "Delete Plan"}
          </button>
        </div>
      </form>
    </div>
  );
}
