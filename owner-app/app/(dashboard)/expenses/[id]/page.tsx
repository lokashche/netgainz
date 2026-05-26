"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter, useParams } from "next/navigation";
import type { GymExpense, ExpenseFrequency } from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const FREQUENCIES: ExpenseFrequency[] = ["Monthly", "Quarterly", "Annually"];

function formatAmount(amount?: number): string {
  if (amount === undefined || amount === null) return "—";
  return Number(amount).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export default function ExpenseDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [expense, setExpense] = useState<GymExpense | null>(null);
  const [date, setDate] = useState("");
  const [category, setCategory] = useState("");
  const [amount, setAmount] = useState("");
  const [vendor, setVendor] = useState("");
  const [is_recurring, setIsRecurring] = useState(false);
  const [frequency, setFrequency] = useState<ExpenseFrequency>("Monthly");
  const [notes, setNotes] = useState("");

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function populateForm(exp: GymExpense) {
    setExpense(exp);
    setDate(exp.date ?? "");
    setCategory(exp.category ?? "");
    setAmount(exp.amount !== undefined ? String(exp.amount) : "");
    setVendor(exp.vendor ?? "");
    setIsRecurring(exp.is_recurring === 1);
    setFrequency((exp.frequency as ExpenseFrequency) || "Monthly");
    setNotes(exp.notes ?? "");
  }

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/expenses/${encodeURIComponent(id)}`);
        if (!res.ok) {
          setError(`Failed to load expense (${res.status})`);
          setLoading(false);
          return;
        }
        const body = await res.json() as { data?: GymExpense };
        const exp = body.data;
        if (!exp) {
          setError("Expense not found");
          setLoading(false);
          return;
        }
        populateForm(exp);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unexpected error");
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
    setSuccess(null);

    const payload: Record<string, string | number> = {
      date,
      category,
      amount: parseFloat(amount),
      is_recurring: is_recurring ? 1 : 0,
    };
    if (vendor) payload.vendor = vendor;
    if (is_recurring) payload.frequency = frequency;
    if (notes) payload.notes = notes;

    try {
      const res = await fetch(`/api/expenses/${encodeURIComponent(id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { message?: string };
        setError(body.message ?? `Error ${res.status}`);
        setSubmitting(false);
        return;
      }

      const body = await res.json() as { data?: GymExpense };
      if (body.data) populateForm(body.data);
      setSuccess("Expense updated successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete expense ${id}? This cannot be undone.`)) return;
    setDeleting(true);
    setError(null);

    try {
      const res = await fetch(`/api/expenses/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { message?: string };
        setError(body.message ?? `Error ${res.status}`);
        setDeleting(false);
        return;
      }

      router.push("/expenses");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-2xl">
        <p className="text-[#8A97B2] text-sm">Loading…</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/expenses" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Expenses
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Edit Expense</h1>
      </div>

      {/* Read-only info row */}
      {expense && (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-4 mb-6 flex flex-wrap items-center gap-4">
          <span className="font-mono text-[#5EEAD4] text-sm">{expense.name}</span>
          <span className="text-[#22D38C] text-2xl font-bold">
            ₹{formatAmount(expense.amount)}
          </span>
          {expense.is_recurring === 1 ? (
            <span className="bg-[rgba(94,234,212,0.15)] text-[#5EEAD4] text-xs font-medium px-2.5 py-0.5 rounded-full">
              Recurring
            </span>
          ) : (
            <span className="bg-[rgba(138,151,178,0.15)] text-[#8A97B2] text-xs font-medium px-2.5 py-0.5 rounded-full">
              One-time
            </span>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm">
            {error}
          </div>
        )}
        {success && (
          <div className="bg-[rgba(34,211,140,0.1)] border border-[#22D38C] text-[#22D38C] rounded-lg p-3 text-sm">
            {success}
          </div>
        )}

        {/* Date + Category */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Date</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Category</label>
            <input
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. Rent"
              className={inputClass}
            />
          </div>
        </div>

        {/* Amount + Vendor */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Amount</label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Vendor / Payee</label>
            <input
              type="text"
              value={vendor}
              onChange={(e) => setVendor(e.target.value)}
              placeholder="e.g. MSEB, Landlord"
              className={inputClass}
            />
          </div>
        </div>

        {/* Recurring checkbox */}
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="is_recurring"
            checked={is_recurring}
            onChange={(e) => setIsRecurring(e.target.checked)}
            className="w-4 h-4 rounded accent-[#22D38C] cursor-pointer"
          />
          <label htmlFor="is_recurring" className="text-sm text-[#E6EDF7] cursor-pointer">
            Recurring expense
          </label>
        </div>

        {/* Frequency — only when recurring */}
        {is_recurring && (
          <div>
            <label className={labelClass}>Frequency</label>
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value as ExpenseFrequency)}
              className={inputClass}
            >
              {FREQUENCIES.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </div>
        )}

        {/* Notes */}
        <div>
          <label className={labelClass}>Notes</label>
          <textarea
            rows={4}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Any additional details"
            className={`${inputClass} resize-none`}
          />
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting || deleting}
            className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            {submitting ? "Saving…" : "Save Changes"}
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={submitting || deleting}
            className="border border-[#F87171] text-[#F87171] rounded-lg py-2 px-4 hover:bg-[rgba(248,113,113,0.1)] text-sm transition-colors disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Delete Expense"}
          </button>
          <a
            href="/expenses"
            className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
          >
            Cancel
          </a>
        </div>
      </form>
    </div>
  );
}
