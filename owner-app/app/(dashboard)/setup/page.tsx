"use client";

import { useEffect, useState, SyntheticEvent } from "react";
import Link from "next/link";
import { extractFrappeError } from "@/lib/frappe";
import type { SetupStatus } from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const BUSINESS_TYPES = ["Proprietorship", "Partnership", "LLP", "Private Limited"];

// One line per checklist step: why it matters.
const HINTS: Record<string, string> = {
  business: "Your business name, financial year and books. Payment methods and your first branch are set up with it.",
  owner_login: "A login in your own name, as Owner. Use it from now on instead of the admin login.",
  branches: "Your first branch, “Main”, is made for you. Rename it or add more.",
  plans: "What members pay for: monthly, quarterly, yearly.",
  profit_first: "Switch on Profit First and check your target percentages.",
  members: "Bring in your existing members from a spreadsheet.",
};

/**
 * Stage 12.1 — setting up a new gym.
 *
 * First the business itself (what ERPNext's own setup screen used to do in Desk),
 * then a checklist of the screens that finish the job. Nothing here needs Desk.
 */
export default function SetupPage() {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  const [companyName, setCompanyName] = useState("");
  const [fyStartMonth, setFyStartMonth] = useState(4);
  const [constitution, setConstitution] = useState("Proprietorship");
  const [gstRegistered, setGstRegistered] = useState(false);
  const [gstin, setGstin] = useState("");
  const [bankAccount, setBankAccount] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function load() {
      const res = await fetch("/api/setup");
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Could not load setup (${res.status})`);
        return;
      }
      setStatus((body as { message: SetupStatus }).message);
    }
    load();
  }, [version]);

  // While the books are being made, check again every few seconds.
  useEffect(() => {
    if (!status?.running) return;
    const t = setTimeout(() => setVersion((v) => v + 1), 4000);
    return () => clearTimeout(t);
  }, [status]);

  async function handleCreate(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: companyName.trim(),
          fy_start_month: fyStartMonth,
          constitution,
          gst_registered: gstRegistered,
          gstin: gstin.trim(),
          bank_account: bankAccount.trim(),
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      setVersion((v) => v + 1);
    } finally {
      setSaving(false);
    }
  }

  const done = status?.steps.filter((s) => s.done).length ?? 0;

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Set up your gym</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          {status ? `${done} of ${status.steps.length} done.` : "Loading…"}
        </p>
      </div>

      {error && (
        <div className="mb-4 bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm">
          {error}
        </div>
      )}

      {status && !status.company && status.running && (
        <div className="mb-6 bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5 text-sm text-[#E6EDF7]">
          Setting up your books. This takes a minute or two — you can leave this page open.
        </div>
      )}

      {status && !status.company && !status.running && (
        <form onSubmit={handleCreate} className="mb-8 bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5 space-y-4">
          <h2 className="text-lg font-semibold text-[#E6EDF7]">Your business</h2>
          {status.error && (
            <p className="text-sm text-[#F87171]">
              The last try did not finish ({status.error}). Check the details and try again.
            </p>
          )}
          <div>
            <label className={labelClass} htmlFor="company_name">Business name</label>
            <input
              id="company_name"
              className={inputClass}
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="As on your bank account or GST certificate"
              required
            />
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className={labelClass} htmlFor="constitution">Business type</label>
              <select
                id="constitution"
                className={inputClass}
                value={constitution}
                onChange={(e) => setConstitution(e.target.value)}
              >
                {BUSINESS_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="fy_start_month">Financial year starts in</label>
              <select
                id="fy_start_month"
                className={inputClass}
                value={fyStartMonth}
                onChange={(e) => setFyStartMonth(Number(e.target.value))}
              >
                {MONTHS.map((m, i) => (
                  <option key={m} value={i + 1}>{m}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className={labelClass} htmlFor="bank_account">Bank account name (optional)</label>
            <input
              id="bank_account"
              className={inputClass}
              value={bankAccount}
              onChange={(e) => setBankAccount(e.target.value)}
              placeholder="e.g. HDFC Current — UPI and card payments land here"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-[#E6EDF7] min-h-[32px]">
            <input
              type="checkbox"
              checked={gstRegistered}
              onChange={(e) => setGstRegistered(e.target.checked)}
              className="w-4 h-4 accent-[#22D38C]"
            />
            We are registered for GST
          </label>
          {gstRegistered && (
            <div>
              <label className={labelClass} htmlFor="gstin">GSTIN</label>
              <input
                id="gstin"
                className={inputClass}
                value={gstin}
                onChange={(e) => setGstin(e.target.value.toUpperCase())}
                placeholder="15 characters"
                maxLength={15}
                required
              />
            </div>
          )}
          <button
            type="submit"
            disabled={saving}
            className="w-full sm:w-auto px-5 py-2.5 rounded-lg text-sm font-semibold bg-[#22D38C] text-[#0B1220] hover:opacity-90 disabled:opacity-50"
          >
            {saving ? "Starting…" : "Create my business"}
          </button>
        </form>
      )}

      {status && (
        <ol className="space-y-3">
          {status.steps.map((s, i) => {
            const locked = !status.company && s.key !== "business";
            return (
              <li
                key={s.key}
                className={`bg-[#111A2E] border border-[#1E2D45] rounded-xl p-4 flex items-start gap-3 ${locked ? "opacity-50" : ""}`}
              >
                <span
                  className={`mt-0.5 flex-none w-6 h-6 rounded-full text-xs font-semibold flex items-center justify-center ${
                    s.done ? "bg-[#22D38C] text-[#0B1220]" : "border border-[#1E2D45] text-[#8A97B2]"
                  }`}
                  aria-label={s.done ? "Done" : "Not done"}
                >
                  {s.done ? "✓" : i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[#E6EDF7] font-medium">{s.label}</p>
                  <p className="text-[#8A97B2] text-xs mt-1">{HINTS[s.key]}</p>
                </div>
                {!locked && s.key !== "business" && (
                  <Link href={s.href} className="text-sm text-[#22D38C] hover:underline flex-none">
                    {s.done ? "Review" : "Open"}
                  </Link>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
