"use client";

import { useState, useEffect, SyntheticEvent } from "react";
import { extractFrappeError } from "@/lib/frappe";
import type { AccountingMethod, GymSettings } from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function SettingsPage() {
  const [accounting_method, setAccountingMethod] = useState<AccountingMethod>("Cash");
  const [member_id_prefix, setMemberIdPrefix] = useState("MEM-");
  const [originalMethod, setOriginalMethod] = useState<AccountingMethod>("Cash");

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/settings");
        if (!res.ok) {
          setError(`Failed to load settings (${res.status})`);
          return;
        }
        const body = (await res.json()) as { data?: GymSettings };
        const s = body.data;
        if (s) {
          setAccountingMethod(s.accounting_method);
          setOriginalMethod(s.accounting_method);
          setMemberIdPrefix(s.member_id_prefix);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unexpected error");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();

    if (accounting_method !== originalMethod) {
      const ok = confirm(
        `Changing the accounting method from ${originalMethod} to ${accounting_method} will retroactively change how all past income is calculated on the dashboard and reports. Continue?`
      );
      if (!ok) return;
    }

    setSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accounting_method, member_id_prefix }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }

      setOriginalMethod(accounting_method);
      setSuccess("Settings saved.");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
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
      <h1 className="text-2xl font-bold text-[#E6EDF7] mb-6">Settings</h1>

      <form
        onSubmit={handleSubmit}
        className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-6"
      >
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

        {/* Accounting */}
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[#22D38C] mb-3">
            Accounting
          </h2>

          <label className={labelClass}>
            Accounting Method <span className="text-[#F87171]">*</span>
          </label>
          <select
            required
            value={accounting_method}
            onChange={(e) => setAccountingMethod(e.target.value as AccountingMethod)}
            className={inputClass}
          >
            <option value="Cash">Cash basis</option>
            <option value="Accrual">Accrual basis</option>
          </select>

          <div className="mt-3 space-y-2 text-xs text-[#8A97B2] leading-relaxed">
            <p>
              <span className="text-[#E6EDF7] font-medium">Cash basis</span> — income is
              recorded when the subscription is <em>paid</em>. Aligns with Profit First.
              Allowed for proprietorships and small businesses under IT Act s.145.
            </p>
            <p>
              <span className="text-[#E6EDF7] font-medium">Accrual basis</span> — income
              is recorded for the month the subscription is <em>for</em>, regardless of
              when collected. Required for most Pvt Ltds and partnerships under Companies
              Act 2013.
            </p>
            <p className="text-[#F87171]">
              Once chosen, the same method must be used consistently year-over-year for
              tax filing.
            </p>
          </div>
        </section>

        <hr className="border-[#1E2D45]" />

        {/* Member Naming */}
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[#22D38C] mb-3">
            Member Naming
          </h2>

          <label className={labelClass}>
            Member ID Prefix <span className="text-[#F87171]">*</span>
          </label>
          <input
            type="text"
            required
            value={member_id_prefix}
            onChange={(e) => setMemberIdPrefix(e.target.value)}
            placeholder="MEM-"
            className={inputClass}
          />
          <p className="mt-2 text-xs text-[#8A97B2]">
            New members will be named {member_id_prefix || "PREFIX"}0001, {member_id_prefix || "PREFIX"}0002, …
          </p>
        </section>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            {submitting ? "Saving…" : "Save Settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
