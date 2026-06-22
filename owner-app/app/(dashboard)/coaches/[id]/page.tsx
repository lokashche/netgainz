"use client";

import { useState, useEffect, SyntheticEvent, use } from "react";
import { useRouter } from "next/navigation";
import type { Coach, CoachStatus, CoachCommissionType } from "@/lib/types";
import { decodeId, extractFrappeError, toIntlPhone } from "@/lib/frappe";

const SPECIALIZATIONS = ["Strength", "Cardio", "Functional", "Sport-Specific", "Yoga", "General"];
const COMMISSION_TYPES: CoachCommissionType[] = ["None", "Fixed", "Per Member", "Percentage"];
const STATUSES: CoachStatus[] = ["Active", "Inactive"];

type Params = Promise<{ id: string }>;

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function CoachDetailPage({ params }: { params: Params }) {
  const { id: rawId } = use(params);
  const id = decodeId(rawId);
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
  const [coach_name, setCoachName] = useState("");
  const [date_of_joining, setDateOfJoining] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [monthly_salary, setMonthlySalary] = useState("");
  const [commission_type, setCommissionType] = useState<CoachCommissionType>("None");
  const [commission_amount, setCommissionAmount] = useState("");
  const [status, setStatus] = useState<CoachStatus>("Active");

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/coaches/${encodeURIComponent(id)}`);
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const body = await res.json() as { data?: Coach };
        const c = body.data;
        if (!c) throw new Error("Coach not found");
        setCoachName(c.coach_name ?? "");
        setDateOfJoining(c.date_of_joining ?? "");
        setPhone(c.phone ?? "");
        setEmail(c.email ?? "");
        setSpecialization(c.specialization ?? "");
        setMonthlySalary(c.monthly_salary != null ? String(c.monthly_salary) : "");
        setCommissionType(c.commission_type ?? "None");
        setCommissionAmount(c.commission_amount != null ? String(c.commission_amount) : "");
        setStatus(c.status ?? "Active");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load coach");
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
    setSuccess(false);

    const payload: Record<string, string | number> = { status, commission_type };
    payload.date_of_joining = date_of_joining;
    payload.phone = phone ? toIntlPhone(phone) : "";
    payload.email = email;
    payload.specialization = specialization;
    payload.monthly_salary = monthly_salary ? Number(monthly_salary) : 0;
    payload.commission_amount =
      commission_type === "None" ? 0 : commission_amount ? Number(commission_amount) : 0;

    try {
      const res = await fetch(`/api/coaches/${encodeURIComponent(id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
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
    if (!confirm(`Delete coach ${id}? This cannot be undone.`)) return;
    setDeleting(true);
    setError(null);

    try {
      const res = await fetch(`/api/coaches/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setDeleting(false);
        return;
      }

      router.push("/coaches");
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
        <a href="/coaches" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Coaches
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">
          Coach{" "}
          <span className="font-mono text-[#5EEAD4] text-sm bg-[#1A2540] px-2 py-0.5 rounded-md">
            {coach_name || id}
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
            Coach updated successfully.
          </div>
        )}

        {/* Coach Name — read-only (this is the document ID) */}
        <div>
          <label className={labelClass}>Coach Name</label>
          <div className="w-full px-3 py-2.5 rounded-lg text-sm bg-[#1A2540] border border-[#1E2D45] text-[#8A97B2]">
            {coach_name}
          </div>
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
              href="/coaches"
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
            {deleting ? "Deleting…" : "Delete Coach"}
          </button>
        </div>
      </form>
    </div>
  );
}
