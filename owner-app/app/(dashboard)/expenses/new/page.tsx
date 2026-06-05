"use client";

import { useState, SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import type { ExpenseCategory, ExpenseFrequency } from "@/lib/types";
import { extractFrappeError } from "@/lib/frappe";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";

async function fetchCategories(q: string): Promise<LinkFieldOption[]> {
  const url = q
    ? `/api/expense-categories?q=${encodeURIComponent(q)}`
    : "/api/expense-categories";
  const res = await fetch(url);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: ExpenseCategory[] };
  return (body.data ?? []).map((c) => ({
    id: c.name,
    label: c.category_name,
    sub: c.description || undefined,
  }));
}

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const FREQUENCIES: ExpenseFrequency[] = ["Monthly", "Quarterly", "Annually"];

export default function NewExpensePage() {
  const router = useRouter();

  const today = new Date().toISOString().split("T")[0];

  const [date, setDate] = useState(today);
  const [category, setCategory] = useState("");
  const [amount, setAmount] = useState("");
  const [vendor, setVendor] = useState("");
  const [is_recurring, setIsRecurring] = useState(false);
  const [frequency, setFrequency] = useState<ExpenseFrequency>("Monthly");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

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
      const res = await fetch("/api/expenses", {
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
      router.push(name ? `/expenses/${name}` : "/expenses");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/expenses" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Expenses
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Add Expense</h1>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm">
            {error}
          </div>
        )}

        {/* Date + Category */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>
              Date <span className="text-[#F87171]">*</span>
            </label>
            <input
              type="date"
              required
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>
              Category <span className="text-[#F87171]">*</span>
            </label>
            <LinkFieldPicker
              value={category}
              onChange={(id) => setCategory(id)}
              fetchOptions={fetchCategories}
              placeholder="Search categories…"
              required
              emptyHint="No categories found"
              inputClassName={inputClass}
            />
          </div>
        </div>

        {/* Amount + Vendor */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>
              Amount <span className="text-[#F87171]">*</span>
            </label>
            <input
              type="number"
              required
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
        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            {submitting ? "Saving…" : "Save Expense"}
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
