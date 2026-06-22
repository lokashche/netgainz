"use client";

import { useState, SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import type { CoachStatus, CoachCommissionType } from "@/lib/types";
import { extractFrappeError, toIntlPhone } from "@/lib/frappe";

const SPECIALIZATIONS = ["Strength", "Cardio", "Functional", "Sport-Specific", "Yoga", "General"];
const COMMISSION_TYPES: CoachCommissionType[] = ["None", "Fixed", "Per Member", "Percentage"];
const STATUSES: CoachStatus[] = ["Active", "Inactive"];

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function NewCoachPage() {
  const router = useRouter();

  const [coach_name, setCoachName] = useState("");
  const [date_of_joining, setDateOfJoining] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [monthly_salary, setMonthlySalary] = useState("");
  const [commission_type, setCommissionType] = useState<CoachCommissionType>("None");
  const [commission_amount, setCommissionAmount] = useState("");
  const [status, setStatus] = useState<CoachStatus>("Active");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: Record<string, string | number> = { coach_name, status, commission_type };
    if (date_of_joining) payload.date_of_joining = date_of_joining;
    if (phone) payload.phone = toIntlPhone(phone);
    if (email) payload.email = email;
    if (specialization) payload.specialization = specialization;
    if (monthly_salary) payload.monthly_salary = Number(monthly_salary);
    if (commission_type !== "None" && commission_amount) {
      payload.commission_amount = Number(commission_amount);
    }

    try {
      const res = await fetch("/api/coaches", {
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
      router.push(name ? `/coaches/${name}` : "/coaches");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/coaches" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Coaches
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Add Coach</h1>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}

        {/* Coach Name */}
        <div>
          <label className={labelClass}>
            Coach Name <span className="text-[#F87171]">*</span>
          </label>
          <input
            type="text"
            required
            value={coach_name}
            onChange={(e) => setCoachName(e.target.value)}
            className={inputClass}
          />
        </div>

        {/* Phone + Email */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Phone</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91 XXXXXXXXXX"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
          </div>
        </div>

        {/* Date of Joining + Specialization */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Date of Joining</label>
            <input
              type="date"
              value={date_of_joining}
              onChange={(e) => setDateOfJoining(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Specialization</label>
            <select
              value={specialization}
              onChange={(e) => setSpecialization(e.target.value)}
              className={inputClass}
            >
              <option value="">Select…</option>
              {SPECIALIZATIONS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Monthly Salary */}
        <div>
          <label className={labelClass}>Monthly Salary</label>
          <input
            type="number"
            min="0"
            step="0.01"
            value={monthly_salary}
            onChange={(e) => setMonthlySalary(e.target.value)}
            placeholder="0"
            className={inputClass}
          />
        </div>

        {/* Commission Type + Status */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Commission Type</label>
            <select
              value={commission_type}
              onChange={(e) => setCommissionType(e.target.value as CoachCommissionType)}
              className={inputClass}
            >
              {COMMISSION_TYPES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as CoachStatus)}
              className={inputClass}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Commission Amount — shown only when commission_type !== None */}
        {commission_type !== "None" && (
          <div>
            <label className={labelClass}>
              Commission Amount{" "}
              <span className="text-[#8A97B2] normal-case tracking-normal">
                (₹ for Fixed/Per Member, % for Percentage)
              </span>
            </label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={commission_amount}
              onChange={(e) => setCommissionAmount(e.target.value)}
              placeholder="0"
              className={inputClass}
            />
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            {submitting ? "Saving…" : "Save Coach"}
          </button>
          <a
            href="/coaches"
            className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
          >
            Cancel
          </a>
        </div>
      </form>
    </div>
  );
}
