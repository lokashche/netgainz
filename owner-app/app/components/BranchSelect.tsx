"use client";

import { useBranches } from "@/lib/useBranches";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

/**
 * Stage 10.2 — which branch a record belongs to.
 *
 * Renders nothing for a one-branch gym: the backend files everything under the
 * default branch, so there is no choice to make. With several branches it shows
 * the default branch until the user picks another. An empty `value` means "let the
 * backend decide" (the default branch, or the member's home branch).
 */
export default function BranchSelect({
  value,
  onChange,
  label = "Branch",
  hint,
}: {
  value: string;
  onChange: (branch: string) => void;
  label?: string;
  hint?: string;
}) {
  const { branches, defaultBranch, multi } = useBranches();
  if (!multi) return null;

  return (
    <div>
      <label className={labelClass}>{label}</label>
      <select
        value={value || defaultBranch}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
      >
        {branches.map((b) => (
          <option key={b.name} value={b.name}>
            {b.branch_name}
          </option>
        ))}
      </select>
      {hint && <p className="text-[#8A97B2] text-xs mt-1">{hint}</p>}
    </div>
  );
}
