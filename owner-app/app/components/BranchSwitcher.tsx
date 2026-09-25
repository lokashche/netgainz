"use client";

import { useEffect, useState } from "react";
import { useBranches } from "@/lib/useBranches";

/**
 * Stage 10.3 — "All branches" or one branch, for the whole owner app.
 *
 * Hidden for a one-branch gym. The choice is kept in a cookie that server pages
 * and the BFF routes pass to the backend, so every list and figure follows it; the
 * page reloads on change so everything already on screen follows too.
 */
export default function BranchSwitcher({ className = "" }: { className?: string }) {
  const { branches, multi } = useBranches();
  const [current, setCurrent] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/branches/current")
      .then((res) => (res.ok ? res.json() : null))
      .then((body: { branch?: string } | null) => {
        if (alive) setCurrent(body?.branch ?? "");
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (!multi || current === null) return null;

  // A remembered branch that was since switched off or renamed shows as "All".
  const value = branches.some((b) => b.name === current) ? current : "";

  async function change(branch: string) {
    await fetch("/api/branches/current", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ branch }),
    });
    window.location.reload();
  }

  return (
    <select
      aria-label="Branch"
      value={value}
      onChange={(e) => change(e.target.value)}
      className={`text-sm rounded-lg px-2.5 py-2 bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] focus:outline-none focus:ring-2 focus:ring-[#22D38C] max-w-[8rem] sm:max-w-[11rem] truncate ${className}`}
    >
      <option value="">All branches</option>
      {branches.map((b) => (
        <option key={b.name} value={b.name}>
          {b.branch_name}
        </option>
      ))}
    </select>
  );
}
