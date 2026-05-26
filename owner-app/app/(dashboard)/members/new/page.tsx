"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { MemberStatus } from "@/lib/types";

const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"];
const CATEGORIES = ["Sport", "General"];
const SOURCES = ["Walk-in", "Social Media", "Referral", "Google", "Other"];
const STATUSES: MemberStatus[] = ["Active", "Inactive", "Frozen"];

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function NewMemberPage() {
  const router = useRouter();

  const [full_name, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [date_of_birth, setDob] = useState("");
  const [blood_group, setBloodGroup] = useState("");
  const [address, setAddress] = useState("");
  const [emergency_contact, setEmergencyContact] = useState("");
  const [date_of_joining, setDateOfJoining] = useState("");
  const [category, setCategory] = useState("");
  const [source_of_reference, setSource] = useState("");
  const [status, setStatus] = useState<MemberStatus>("Active");
  const [inactive_reason, setInactiveReason] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: Record<string, string> = { full_name, status };
    if (phone) payload.phone = phone;
    if (email) payload.email = email;
    if (date_of_birth) payload.date_of_birth = date_of_birth;
    if (blood_group) payload.blood_group = blood_group;
    if (address) payload.address = address;
    if (emergency_contact) payload.emergency_contact = emergency_contact;
    if (date_of_joining) payload.date_of_joining = date_of_joining;
    if (category) payload.category = category;
    if (source_of_reference) payload.source_of_reference = source_of_reference;
    if (status === "Inactive" && inactive_reason) payload.inactive_reason = inactive_reason;

    try {
      const res = await fetch("/api/members", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { message?: string };
        setError(body.message ?? `Error ${res.status}`);
        setSubmitting(false);
        return;
      }

      const body = await res.json() as { data?: { name?: string } };
      const name = body?.data?.name;
      router.push(name ? `/members/${name}` : "/members");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/members" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Members
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Add Member</h1>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}

        {/* Full Name */}
        <div>
          <label className={labelClass}>
            Full Name <span className="text-[#F87171]">*</span>
          </label>
          <input
            type="text"
            required
            value={full_name}
            onChange={(e) => setFullName(e.target.value)}
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

        {/* Date of Birth + Blood Group */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Date of Birth</label>
            <input
              type="date"
              value={date_of_birth}
              onChange={(e) => setDob(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Blood Group</label>
            <select
              value={blood_group}
              onChange={(e) => setBloodGroup(e.target.value)}
              className={inputClass}
            >
              <option value="">Select…</option>
              {BLOOD_GROUPS.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Address */}
        <div>
          <label className={labelClass}>Address</label>
          <textarea
            rows={3}
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className={`${inputClass} resize-none`}
          />
        </div>

        {/* Emergency Contact */}
        <div>
          <label className={labelClass}>Emergency Contact</label>
          <input
            type="tel"
            value={emergency_contact}
            onChange={(e) => setEmergencyContact(e.target.value)}
            className={inputClass}
          />
        </div>

        {/* Date of Joining + Category */}
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
            <label className={labelClass}>Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={inputClass}
            >
              <option value="">Select…</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Source of Reference */}
        <div>
          <label className={labelClass}>Source of Reference</label>
          <select
            value={source_of_reference}
            onChange={(e) => setSource(e.target.value)}
            className={inputClass}
          >
            <option value="">Select…</option>
            {SOURCES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {/* Status */}
        <div>
          <label className={labelClass}>Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as MemberStatus)}
            className={inputClass}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {/* Inactive Reason — shown only when status = Inactive */}
        {status === "Inactive" && (
          <div>
            <label className={labelClass}>Reason for Inactivity</label>
            <textarea
              rows={3}
              value={inactive_reason}
              onChange={(e) => setInactiveReason(e.target.value)}
              className={`${inputClass} resize-none`}
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
            {submitting ? "Saving…" : "Save Member"}
          </button>
          <a
            href="/members"
            className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
          >
            Cancel
          </a>
        </div>
      </form>
    </div>
  );
}
