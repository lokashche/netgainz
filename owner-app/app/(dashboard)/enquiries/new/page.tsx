"use client";

import { useState, SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { extractFrappeError } from "@/lib/frappe";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";
import type { EnquirySource, Member, Program } from "@/lib/types";

async function fetchPrograms(q: string): Promise<LinkFieldOption[]> {
  const params = new URLSearchParams({ active_only: "1" });
  if (q) params.set("q", q);
  const res = await fetch(`/api/programs?${params.toString()}`);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: Program[] };
  return (body.data ?? []).map((p) => ({ id: p.name, label: p.program_name }));
}

async function fetchMembers(q: string): Promise<LinkFieldOption[]> {
  const url = q ? `/api/members?q=${encodeURIComponent(q)}` : "/api/members";
  const res = await fetch(url);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: Member[] };
  return (body.data ?? []).map((m) => ({
    id: m.name,
    label: m.full_name,
    sub: m.phone || m.email || undefined,
  }));
}

const SOURCES: EnquirySource[] = ["Walk-in", "Instagram", "Referral", "Other"];

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function NewEnquiryPage() {
  const router = useRouter();

  const [full_name, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [source, setSource] = useState<EnquirySource>("Walk-in");
  const [referred_by, setReferredBy] = useState("");
  const [referredByLabel, setReferredByLabel] = useState("");
  const [interested_program, setProgram] = useState("");
  const [programLabel, setProgramLabel] = useState("");
  const [next_follow_up, setFollowUp] = useState("");
  const [notes, setNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: Record<string, string> = { full_name, source };
    if (phone) payload.phone = phone;
    if (email) payload.email = email;
    if (source === "Referral" && referred_by) payload.referred_by = referred_by;
    if (interested_program) payload.interested_program = interested_program;
    if (next_follow_up) payload.next_follow_up = next_follow_up;
    if (notes) payload.notes = notes;

    try {
      const res = await fetch("/api/enquiries", {
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
      router.push("/enquiries");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <Link
          href="/enquiries"
          className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors"
        >
          ← Back to Enquiries
        </Link>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">New Enquiry</h1>
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5"
      >
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}

        <div>
          <label className={labelClass}>
            Full Name <span className="text-[#F87171]">*</span>
          </label>
          <input
            type="text"
            required
            autoFocus
            value={full_name}
            onChange={(e) => setFullName(e.target.value)}
            className={inputClass}
          />
        </div>

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

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>How did they hear of you?</label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as EnquirySource)}
              className={inputClass}
            >
              {SOURCES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          {source === "Referral" && (
            <div>
              <label className={labelClass}>Referred By</label>
              <LinkFieldPicker
                value={referred_by}
                displayLabel={referredByLabel}
                onChange={(id, label) => {
                  setReferredBy(id);
                  setReferredByLabel(label);
                }}
                fetchOptions={fetchMembers}
                placeholder="Search members…"
                emptyHint="No members found"
                inputClassName={inputClass}
              />
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Interested Program</label>
            <LinkFieldPicker
              value={interested_program}
              displayLabel={programLabel}
              onChange={(id, label) => {
                setProgram(id);
                setProgramLabel(label);
              }}
              fetchOptions={fetchPrograms}
              placeholder="Search programs…"
              emptyHint="No programs found"
              inputClassName={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Next Follow-up</label>
            <input
              type="date"
              value={next_follow_up}
              onChange={(e) => setFollowUp(e.target.value)}
              className={inputClass}
            />
            <p className="text-xs text-[#8A97B2] mt-1">
              When to call or message them next.
            </p>
          </div>
        </div>

        <div>
          <label className={labelClass}>Notes</label>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="What they asked, what was quoted…"
            className={`${inputClass} resize-none`}
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            {submitting ? "Saving…" : "Save Enquiry"}
          </button>
          <Link
            href="/enquiries"
            className="px-5 py-2 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
