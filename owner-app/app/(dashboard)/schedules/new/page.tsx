"use client";

import { useState, SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";
import { useClassTerm } from "@/lib/useClassTerm";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";
import type { Coach, Program } from "@/lib/types";

async function fetchPrograms(q: string): Promise<LinkFieldOption[]> {
  const params = new URLSearchParams({ active_only: "1" });
  if (q) params.set("q", q);
  const res = await fetch(`/api/programs?${params.toString()}`);
  if (!res.ok) return [];
  const body = (await res.json()) as { data?: Program[] };
  return (body.data ?? []).map((p) => ({ id: p.name, label: p.program_name }));
}

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

const DAY_DEFS: { key: string; field: string; label: string }[] = [
  { key: "monday", field: "on_monday", label: "Mon" },
  { key: "tuesday", field: "on_tuesday", label: "Tue" },
  { key: "wednesday", field: "on_wednesday", label: "Wed" },
  { key: "thursday", field: "on_thursday", label: "Thu" },
  { key: "friday", field: "on_friday", label: "Fri" },
  { key: "saturday", field: "on_saturday", label: "Sat" },
  { key: "sunday", field: "on_sunday", label: "Sun" },
];

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

export default function NewSchedulePage() {
  const router = useRouter();
  const { singular, plural } = useClassTerm();

  const [title, setTitle] = useState("");
  const [program, setProgram] = useState("");
  const [programLabel, setProgramLabel] = useState("");
  const [coach, setCoach] = useState("");
  const [coachLabel, setCoachLabel] = useState("");
  const [start_time, setStartTime] = useState("07:30");
  const [duration_mins, setDuration] = useState("60");
  const [capacity, setCapacity] = useState("0");
  const [days, setDays] = useState<Record<string, boolean>>({
    monday: false,
    tuesday: false,
    wednesday: false,
    thursday: false,
    friday: false,
    saturday: false,
    sunday: false,
  });
  const [is_active, setIsActive] = useState(true);
  const [notes, setNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleDay(key: string) {
    setDays((d) => ({ ...d, [key]: !d[key] }));
  }

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (!DAY_DEFS.some((d) => days[d.key])) {
      setError("Select at least one day for the class to repeat on.");
      return;
    }

    setSubmitting(true);
    const payload: Record<string, string | number> = {
      title,
      start_time: `${start_time}:00`,
      duration_mins: Number(duration_mins),
      capacity: Number(capacity),
      is_active: is_active ? 1 : 0,
    };
    if (program) payload.program = program;
    if (coach) payload.coach = coach;
    if (notes) payload.notes = notes;
    for (const d of DAY_DEFS) payload[d.field] = days[d.key] ? 1 : 0;

    try {
      const res = await fetch("/api/class-schedules", {
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
      const body = (await res.json()) as { data?: { name?: string } };
      const name = body?.data?.name;
      router.push(name ? `/schedules/${name}` : "/schedules");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/schedules" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to {singular} Schedules
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">New {singular} Schedule</h1>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">
            {error}
          </div>
        )}

        <div>
          <label className={labelClass}>
            Title <span className="text-[#F87171]">*</span>
          </label>
          <input type="text" required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Morning Batch" className={inputClass} />
        </div>

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

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className={labelClass}>
              Start Time <span className="text-[#F87171]">*</span>
            </label>
            <input type="time" required value={start_time} onChange={(e) => setStartTime(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Duration (mins)</label>
            <input type="number" min="1" value={duration_mins} onChange={(e) => setDuration(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Capacity</label>
            <input type="number" min="0" value={capacity} onChange={(e) => setCapacity(e.target.value)} className={inputClass} />
            <p className="mt-1 text-xs text-[#8A97B2]">0 = unlimited</p>
          </div>
        </div>

        <div>
          <label className={labelClass}>
            Repeat On <span className="text-[#F87171]">*</span>
          </label>
          <div className="flex flex-wrap gap-2">
            {DAY_DEFS.map((d) => (
              <button
                key={d.key}
                type="button"
                onClick={() => toggleDay(d.key)}
                className={
                  days[d.key]
                    ? "px-3 py-1.5 text-sm font-semibold rounded-lg bg-[#22D38C] text-[#0B1220]"
                    : "px-3 py-1.5 text-sm font-medium rounded-lg bg-[#1A2540] border border-[#1E2D45] text-[#8A97B2] hover:text-[#E6EDF7]"
                }
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className={labelClass}>Notes</label>
          <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional notes…" className={`${inputClass} resize-none`} />
        </div>

        <div className="flex items-center gap-2">
          <input id="is_active" type="checkbox" checked={is_active} onChange={(e) => setIsActive(e.target.checked)} className="w-4 h-4 rounded accent-[#22D38C] cursor-pointer" />
          <label htmlFor="is_active" className="text-sm text-[#E6EDF7] cursor-pointer">
            Active
          </label>
        </div>

        <p className="text-xs text-[#8A97B2]">
          Saving creates the upcoming {plural.toLowerCase()} automatically; a daily job keeps the
          next couple of weeks topped up.
        </p>

        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={submitting} className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-6 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors">
            {submitting ? "Saving…" : "Save Schedule"}
          </button>
          <a href="/schedules" className="px-6 py-2.5 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors">
            Cancel
          </a>
        </div>
      </form>
    </div>
  );
}
