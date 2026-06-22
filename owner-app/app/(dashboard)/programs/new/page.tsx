"use client";

import { useState, SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function NewProgramPage() {
  const router = useRouter();

  const [program_name, setProgramName] = useState("");
  const [description, setDescription] = useState("");
  const [is_active, setIsActive] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: Record<string, string | number> = {
      program_name,
      is_active: is_active ? 1 : 0,
    };
    if (description) payload.description = description;

    try {
      const res = await fetch("/api/programs", {
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
      router.push(name ? `/programs/${name}` : "/programs");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/programs" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Programs
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Add Program</h1>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}

        {/* Program Name */}
        <div>
          <label className={labelClass}>
            Program Name <span className="text-[#F87171]">*</span>
          </label>
          <input
            type="text"
            required
            value={program_name}
            onChange={(e) => setProgramName(e.target.value)}
            className={inputClass}
          />
        </div>

        {/* Description */}
        <div>
          <label className={labelClass}>Description</label>
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={`${inputClass} resize-none`}
          />
        </div>

        {/* Active */}
        <div className="flex items-center gap-2">
          <input
            id="is_active"
            type="checkbox"
            checked={is_active}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 rounded accent-[#22D38C] cursor-pointer"
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
            {submitting ? "Saving…" : "Save Program"}
          </button>
          <a
            href="/programs"
            className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
          >
            Cancel
          </a>
        </div>
      </form>
    </div>
  );
}
