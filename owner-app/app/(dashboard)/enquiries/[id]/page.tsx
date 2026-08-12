"use client";

// OP-2: one enquiry — edit, move through the pipeline, and Convert to Member.
// Convert creates the member server-side (one door to "Joined") and lands the
// desk on the enrolment screen with the new member prefilled, where plan,
// price and the DS-4 free trial are decided.

import { useState, useEffect, SyntheticEvent, use } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { extractFrappeError } from "@/lib/frappe";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";
import type {
  ConvertResult,
  Enquiry,
  EnquirySource,
  EnquiryStatus,
  Member,
  Program,
} from "@/lib/types";

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
const STATUSES: EnquiryStatus[] = ["New", "Contacted", "Trial Scheduled", "Lost"];

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

type Params = Promise<{ id: string }>;

export default function EnquiryDetailPage({ params }: { params: Params }) {
  const { id } = use(params);
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [converting, setConverting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [full_name, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [source, setSource] = useState<EnquirySource>("Walk-in");
  const [referred_by, setReferredBy] = useState("");
  const [referredByLabel, setReferredByLabel] = useState("");
  const [interested_program, setProgram] = useState("");
  const [programLabel, setProgramLabel] = useState("");
  const [status, setStatus] = useState<EnquiryStatus>("New");
  const [next_follow_up, setFollowUp] = useState("");
  const [lost_reason, setLostReason] = useState("");
  const [notes, setNotes] = useState("");
  const [member, setMember] = useState<string | null>(null);
  const [joined_on, setJoinedOn] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/enquiries/${encodeURIComponent(id)}`);
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const body = (await res.json()) as { data?: Enquiry };
        const e = body.data;
        if (!e) throw new Error("Enquiry not found");
        setFullName(e.full_name ?? "");
        setPhone(e.phone ?? "");
        setEmail(e.email ?? "");
        setSource(e.source ?? "Walk-in");
        setReferredBy(e.referred_by ?? "");
        setReferredByLabel(e.referred_by ?? "");
        setProgram(e.interested_program ?? "");
        setProgramLabel(e.interested_program ?? "");
        setStatus(e.status ?? "New");
        setFollowUp(e.next_follow_up ?? "");
        setLostReason(e.lost_reason ?? "");
        setNotes(e.notes ?? "");
        setMember(e.member ?? null);
        setJoinedOn(e.joined_on ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load enquiry");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const joined = status === "Joined";

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(false);

    const payload: Record<string, string | null> = {
      full_name,
      phone,
      email,
      source,
      referred_by: source === "Referral" ? referred_by || null : null,
      interested_program: interested_program || null,
      status,
      next_follow_up: next_follow_up || null,
      lost_reason: status === "Lost" ? lost_reason : null,
      notes,
    };

    try {
      const res = await fetch(`/api/enquiries/${encodeURIComponent(id)}`, {
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

  async function handleConvert() {
    setConverting(true);
    setError(null);
    try {
      const res = await fetch(`/api/enquiries/${encodeURIComponent(id)}/convert`, {
        method: "POST",
      });
      const body = (await res.json().catch(() => null)) as ConvertResult | null;
      if (!res.ok || !body?.member) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setConverting(false);
        return;
      }
      const qs = new URLSearchParams({
        member: body.member,
        member_label: body.member_name ?? full_name,
      });
      router.push(`/subscriptions/new?${qs.toString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setConverting(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete enquiry ${id}? This cannot be undone.`)) return;
    setDeleting(true);
    setError(null);
    try {
      const res = await fetch(`/api/enquiries/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setDeleting(false);
        return;
      }
      router.push("/enquiries");
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
        <Link
          href="/enquiries"
          className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors"
        >
          ← Back to Enquiries
        </Link>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">
          Enquiry{" "}
          <span className="font-mono text-[#5EEAD4] text-sm bg-[#1A2540] px-2 py-0.5 rounded-md">
            {id}
          </span>
        </h1>
      </div>

      {joined && member && (
        <div className="mb-6 rounded-lg bg-[rgba(34,211,140,0.1)] border border-[#22D38C] px-4 py-3 text-sm text-[#22D38C]">
          Joined{joined_on ? ` on ${joined_on}` : ""} —{" "}
          <Link href={`/members/${member}`} className="underline font-medium">
            open member {member} →
          </Link>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5"
      >
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-lg bg-[rgba(34,211,140,0.1)] border border-[#22D38C] px-4 py-3 text-sm text-[#22D38C]">
            Enquiry updated.
          </div>
        )}

        <div>
          <label className={labelClass}>
            Full Name <span className="text-[#F87171]">*</span>
          </label>
          <input
            type="text"
            required
            value={full_name}
            onChange={(e) => setFullName(e.target.value)}
            disabled={joined}
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
              disabled={joined}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={joined}
              className={inputClass}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Source</label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as EnquirySource)}
              disabled={joined}
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
                onChange={(rid, label) => {
                  setReferredBy(rid);
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
              onChange={(pid, label) => {
                setProgram(pid);
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
              disabled={joined}
              className={inputClass}
            />
          </div>
        </div>

        {!joined && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as EnquiryStatus)}
                className={inputClass}
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            {status === "Lost" && (
              <div>
                <label className={labelClass}>
                  Lost Reason <span className="text-[#F87171]">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={lost_reason}
                  onChange={(e) => setLostReason(e.target.value)}
                  placeholder="Too expensive / timing / joined elsewhere…"
                  className={inputClass}
                />
              </div>
            )}
          </div>
        )}

        <div>
          <label className={labelClass}>Notes</label>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className={`${inputClass} resize-none`}
          />
        </div>

        <div className="flex items-center justify-between pt-2 flex-wrap gap-3">
          <div className="flex gap-3">
            {!joined && (
              <button
                type="submit"
                disabled={submitting}
                className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
              >
                {submitting ? "Saving…" : "Save Changes"}
              </button>
            )}
            {!joined && (
              <button
                type="button"
                onClick={handleConvert}
                disabled={converting}
                className="border border-[#22D38C] text-[#22D38C] rounded-lg py-2 px-4 text-sm hover:bg-[rgba(34,211,140,0.1)] disabled:opacity-50 transition-colors"
              >
                {converting ? "Converting…" : "Convert to Member →"}
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="border border-[#F87171] text-[#F87171] rounded-lg py-2 px-4 text-sm hover:bg-[rgba(248,113,113,0.1)] disabled:opacity-50 transition-colors"
          >
            {deleting ? "Deleting…" : "Delete Enquiry"}
          </button>
        </div>
      </form>
    </div>
  );
}
