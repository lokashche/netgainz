"use client";

import { useState, useEffect, SyntheticEvent } from "react";
import { decodeId, extractFrappeError } from "@/lib/frappe";
import { useRouter, useParams } from "next/navigation";
import type { ExpenseCategory, PFBucket } from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const PF_BUCKETS: PFBucket[] = [
  "Operating Expenses",
  "Owner's Pay",
  "Tax",
  "Pass-Through",
];

export default function ExpenseCategoryDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = decodeId(params.id);

  const [category, setCategory] = useState<ExpenseCategory | null>(null);
  const [pf_bucket, setPfBucket] = useState<PFBucket>("Operating Expenses");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/expense-categories/${encodeURIComponent(id)}`);
        if (!res.ok) {
          setError(`Failed to load category (${res.status})`);
          setLoading(false);
          return;
        }
        const body = await res.json() as { data?: ExpenseCategory };
        const cat = body.data;
        if (!cat) {
          setError("Category not found");
          setLoading(false);
          return;
        }
        setCategory(cat);
        setPfBucket((cat.pf_bucket ?? "Operating Expenses") as PFBucket);
        setDescription(cat.description ?? "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unexpected error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const res = await fetch(`/api/expense-categories/${encodeURIComponent(id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description, pf_bucket }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setSubmitting(false);
        return;
      }

      setSuccess("Category updated successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete category "${category?.category_name}"? This cannot be undone.`)) return;
    setDeleting(true);
    setError(null);

    try {
      const res = await fetch(`/api/expense-categories/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setDeleting(false);
        return;
      }

      router.push("/expense-categories");
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
        <a href="/expense-categories" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Categories
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">
          {category?.category_name ?? decodeURIComponent(id)}
        </h1>
      </div>

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

        {/* Category Name — read-only (it is the document ID) */}
        <div>
          <label className={labelClass}>Category Name</label>
          <div className="w-full px-3 py-2.5 rounded-lg text-sm bg-[#1A2540] border border-[#1E2D45] text-[#8A97B2] select-none">
            {category?.category_name ?? "—"}
          </div>
          <p className="text-[#8A97B2] text-xs mt-1">Category name cannot be changed after creation.</p>
        </div>

        {/* Profit First bucket */}
        <div>
          <label className={labelClass}>Profit First Bucket</label>
          <select
            value={pf_bucket}
            onChange={(e) => setPfBucket(e.target.value as PFBucket)}
            className={inputClass}
          >
            {PF_BUCKETS.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
          <p className="text-[#8A97B2] text-xs mt-1">
            How expenses here roll up in the Instant Assessment. Choose{" "}
            <span className="text-[#E6EDF7]">Pass-Through</span> for resold
            supplements, third-party trainer payouts or merchandise (excluded from
            Real Revenue).
          </p>
        </div>

        {/* Description */}
        <div>
          <label className={labelClass}>Description</label>
          <textarea
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description for this category"
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
            {deleting ? "Deleting…" : "Delete Category"}
          </button>
          <a
            href="/expense-categories"
            className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
          >
            Cancel
          </a>
        </div>
      </form>
    </div>
  );
}
