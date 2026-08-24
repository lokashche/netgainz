"use client";

import { useState, useEffect, SyntheticEvent, use } from "react";
import { useRouter } from "next/navigation";
import type { Member, MemberStatus } from "@/lib/types";
import { decodeId, extractFrappeError, toIntlPhone } from "@/lib/frappe";
import ProgressPanel from "@/app/components/ProgressPanel";

const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"];
const CATEGORIES = ["Sport", "General"];
const SOURCES = ["Walk-in", "Social Media", "Referral", "Google", "Other"];
const STATUSES: MemberStatus[] = ["Active", "Inactive", "Frozen"];

type Params = Promise<{ id: string }>;

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function MemberDetailPage({ params }: { params: Params }) {
  const { id } = use(params);
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
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
  const [referred_by, setReferredBy] = useState("");
  const [status, setStatus] = useState<MemberStatus>("Active");
  const [inactive_reason, setInactiveReason] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/members/${encodeURIComponent(id)}`);
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const body = await res.json() as { data?: Member };
        const m = body.data;
        if (!m) throw new Error("Member not found");
        setFullName(m.full_name ?? "");
        setPhone(m.phone ?? "");
        setEmail(m.email ?? "");
        setDob(m.date_of_birth ?? "");
        setBloodGroup(m.blood_group ?? "");
        setAddress(m.address ?? "");
        setEmergencyContact(m.emergency_contact ?? "");
        setDateOfJoining(m.date_of_joining ?? "");
        setCategory(m.category ?? "");
        setSource(m.source_of_reference ?? "");
        setReferredBy(m.referred_by ?? "");
        setStatus(m.status ?? "Active");
        setInactiveReason(m.inactive_reason ?? "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load member");
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

    const payload: Record<string, string> = { full_name, status };
    payload.phone = phone ? toIntlPhone(phone) : "";
    payload.email = email;
    payload.date_of_birth = date_of_birth;
    payload.blood_group = blood_group;
    payload.address = address;
    payload.emergency_contact = emergency_contact ? toIntlPhone(emergency_contact) : "";
    payload.date_of_joining = date_of_joining;
    payload.category = category;
    payload.source_of_reference = source_of_reference;
    payload.referred_by = source_of_reference === "Referral" ? referred_by : "";
    payload.inactive_reason = status === "Inactive" ? inactive_reason : "";

    try {
      const res = await fetch(`/api/members/${encodeURIComponent(id)}`, {
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
    if (!confirm(`Delete member ${id}? This cannot be undone.`)) return;
    setDeleting(true);
    setError(null);

    try {
      const res = await fetch(`/api/members/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setDeleting(false);
        return;
      }

      router.push("/members");
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
    <div className="max-w-4xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/members" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to Members
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">
          Member{" "}
          <span className="font-mono text-[#5EEAD4] text-sm bg-[#1A2540] px-2 py-0.5 rounded-md">
            {id}
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
            Member updated successfully.
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
            placeholder="+91 XXXXXXXXXX"
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

        {/* Referred By — shown only when the source is a referral */}
        {source_of_reference === "Referral" && (
          <div>
            <label className={labelClass}>Referred By</label>
            <input
              type="text"
              value={referred_by}
              onChange={(e) => setReferredBy(e.target.value)}
              placeholder="Who referred them?"
              className={inputClass}
            />
          </div>
        )}

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

        {/* Inactive Reason */}
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
              href="/members"
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
            {deleting ? "Deleting…" : "Delete Member"}
          </button>
        </div>
      </form>

      {/* OP-5: measurements, targets and what they add up to. */}
      <ProgressPanel memberId={decodeId(id)} />
    </div>
  );
}
