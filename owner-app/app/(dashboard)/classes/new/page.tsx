"use client";

import { useState, SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";
import { useClassTerm } from "@/lib/useClassTerm";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";
import type { Coach, Program, ClassSessionStatus } from "@/lib/types";

async function fetchCoaches(q: string): Promise<LinkFieldOption[]> {
  const url = q ? `/api/coaches?q=${encodeURIComponent(q)}` : "/api/coaches";
  const res = await fetch(url);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: Coach[] };
  return (body.data ?? []).map((c) => ({
    id: c.name,
    label: c.coach_name,
    sub: c.specialization || c.phone || undefined,
  }));
}

async function fetchPrograms(q: string): Promise<LinkFieldOption[]> {
  const params = new URLSearchParams({ active_only: "1" });
  if (q) params.set("q", q);
  const res = await fetch(`/api/programs?${params.toString()}`);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: Program[] };
  return (body.data ?? []).map((p) => ({
    id: p.name,
    label: p.program_name,
  }));
}

const STATUSES: ClassSessionStatus[] = ["Scheduled", "Completed", "Cancelled"];

const toFrappeDT = (v: string) => (v ? v.replace("T", " ") + ":00" : "");

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function NewClassPage() {
  const router = useRouter();
  const { singular, plural } = useClassTerm();

  const [title, setTitle] = useState("");
  const [program, setProgram] = useState("");
  const [programLabel, setProgramLabel] = useState("");
  const [coach, setCoach] = useState("");
  const [coachLabel, setCoachLabel] = useState("");
  const [start_time, setStartTime] = useState("");
  const [duration_mins, setDurationMins] = useState("60");
  const [capacity, setCapacity] = useState("0");
  const [status, setStatus] = useState<ClassSessionStatus>("Scheduled");
  const [notes, setNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const payload: Record<string, string | number> = {
      title,
      start_time: toFrappeDT(start_time),
      duration_mins: Number(duration_mins),
      capacity: Number(capacity),
      status,
    };
    if (program) payload.program = program;
    if (coach) payload.coach = coach;
    if (notes) payload.notes = notes;

    try {
      const res = await fetch("/api/class-sessions", {
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
      router.push(name ? `/classes/${name}` : "/classes");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/classes" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to {plural}
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Schedule {singular}</h1>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}

        {/* Title */}
        <div>
          <label className={labelClass}>
            Title <span className="text-[#F87171]">*</span>
          </label>
          <input
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputClass}
          />
        </div>

        {/* Program + Coach */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Program</label>
            <LinkFieldPicker
              value={program}
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
            <label className={labelClass}>Coach</label>
            <LinkFieldPicker
              value={coach}
              displayLabel={coachLabel}
              onChange={(id, label) => {
                setCoach(id);
                setCoachLabel(label);
              }}
              fetchOptions={fetchCoaches}
              placeholder="Search coaches…"
              emptyHint="No coaches found"
              inputClassName={inputClass}
            />
          </div>
        </div>

        {/* Start Time */}
        <div>
          <label className={labelClass}>
            Start Time <span className="text-[#F87171]">*</span>
          </label>
          <input
            type="datetime-local"
            required
            value={start_time}
            onChange={(e) => setStartTime(e.target.value)}
            className={inputClass}
          />
        </div>

        {/* Duration + Capacity */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Duration (mins)</label>
            <input
              type="number"
              min="0"
              value={duration_mins}
              onChange={(e) => setDurationMins(e.target.value)}
              placeholder="60"
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Capacity</label>
            <input
              type="number"
              min="0"
              value={capacity}
              onChange={(e) => setCapacity(e.target.value)}
              placeholder="0"
              className={inputClass}
            />
            <p className="text-xs text-[#8A97B2] mt-1">0 = unlimited</p>
          </div>
        </div>

        {/* Status */}
        <div>
          <label className={labelClass}>Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as ClassSessionStatus)}
            className={inputClass}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {/* Notes */}
        <div>
          <label className={labelClass}>Notes</label>
          <textarea
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes…"
            className={`${inputClass} resize-none`}
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            {submitting ? "Saving…" : `Save ${singular}`}
          </button>
          <a
            href="/classes"
            className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors"
          >
            Cancel
          </a>
        </div>
      </form>
    </div>
  );
}
