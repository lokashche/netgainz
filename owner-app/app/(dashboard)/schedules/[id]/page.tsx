"use client";

import { useState, useEffect, SyntheticEvent, use } from "react";
import { useRouter } from "next/navigation";
import { decodeId, extractFrappeError } from "@/lib/frappe";
import { useClassTerm } from "@/lib/useClassTerm";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";
import type { Coach, Program, ClassSchedule } from "@/lib/types";

type Params = Promise<{ id: string }>;

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

const DAY_DEFS: { key: string; field: keyof ClassSchedule; label: string }[] = [
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

export default function ScheduleDetailPage({ params }: { params: Params }) {
  const { id: rawId } = use(params);
  const id = decodeId(rawId);
  const router = useRouter();
  const { singular } = useClassTerm();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [program, setProgram] = useState("");
  const [coach, setCoach] = useState("");
  const [start_time, setStartTime] = useState("07:30");
  const [duration_mins, setDuration] = useState("60");
  const [capacity, setCapacity] = useState("0");
  const [days, setDays] = useState<Record<string, boolean>>({});
  const [is_active, setIsActive] = useState(true);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/class-schedules/${encodeURIComponent(id)}`);
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const body = (await res.json()) as { data?: ClassSchedule };
        const s = body.data;
        if (!s) throw new Error("Schedule not found");
        setTitle(s.title ?? "");
        setProgram(s.program ?? "");
        setCoach(s.coach ?? "");
        setStartTime((s.start_time ?? "07:30:00").slice(0, 5));
        setDuration(String(s.duration_mins ?? 60));
        setCapacity(String(s.capacity ?? 0));
        setIsActive(s.is_active !== 0);
        setNotes(s.notes ?? "");
        const d: Record<string, boolean> = {};
        for (const def of DAY_DEFS) d[def.key] = s[def.field] === 1;
        setDays(d);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load schedule");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  function toggleDay(key: string) {
    setDays((d) => ({ ...d, [key]: !d[key] }));
  }

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!DAY_DEFS.some((d) => days[d.key])) {
      setError("Select at least one day for the class to repeat on.");
      return;
    }

    setSubmitting(true);
    const payload: Record<string, string | number> = {
      title,
      program,
      coach,
      start_time: `${start_time}:00`,
      duration_mins: Number(duration_mins),
      capacity: Number(capacity),
      is_active: is_active ? 1 : 0,
      notes,
    };
    for (const d of DAY_DEFS) payload[d.field] = days[d.key] ? 1 : 0;

    try {
      const res = await fetch(`/api/class-schedules/${encodeURIComponent(id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
      } else {
        setSuccess("Schedule saved.");
        setTimeout(() => setSuccess(null), 3000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await fetch(`/api/class-schedules/${encodeURIComponent(id)}`, { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
      } else {
        const created = (body as { created?: number })?.created ?? 0;
        setSuccess(`Generated ${created} upcoming session${created === 1 ? "" : "s"}.`);
        setTimeout(() => setSuccess(null), 4000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setGenerating(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete schedule ${id}? Already-created sessions are kept.`)) return;
    setDeleting(true);
    setError(null);
    try {
      const res = await fetch(`/api/class-schedules/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setDeleting(false);
        return;
      }
      router.push("/schedules");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-[#8A97B2] text-sm">Loading…</div>
    );
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/schedules" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to {singular} Schedules
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">
          {singular} Schedule{" "}
          <span className="font-mono text-[#5EEAD4] text-sm bg-[#1A2540] px-2 py-0.5 rounded-md">{id}</span>
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8 space-y-5">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171]">{error}</div>
        )}
        {success && (
          <div className="rounded-lg bg-[rgba(34,211,140,0.1)] border border-[#22D38C] px-4 py-3 text-sm text-[#22D38C]">{success}</div>
        )}

        <div>
          <label className={labelClass}>
            Title <span className="text-[#F87171]">*</span>
          </label>
          <input type="text" required value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Program</label>
            <LinkFieldPicker value={program} displayLabel={program} onChange={(pid) => setProgram(pid)} fetchOptions={fetchPrograms} placeholder="Search programs…" emptyHint="No programs found" inputClassName={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Coach</label>
            <LinkFieldPicker value={coach} displayLabel={coach} onChange={(cid) => setCoach(cid)} fetchOptions={fetchCoaches} placeholder="Search coaches…" emptyHint="No coaches found" inputClassName={inputClass} />
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
          <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} className={`${inputClass} resize-none`} />
        </div>

        <div className="flex items-center gap-2">
          <input id="is_active" type="checkbox" checked={is_active} onChange={(e) => setIsActive(e.target.checked)} className="w-4 h-4 rounded accent-[#22D38C] cursor-pointer" />
          <label htmlFor="is_active" className="text-sm text-[#E6EDF7] cursor-pointer">Active</label>
        </div>

        <p className="text-xs text-[#8A97B2]">
          Editing the time or days does not change sessions already created — use “Generate now”
          to add the upcoming ones, and remove any wrong future session from the {singular} list.
        </p>

        <div className="flex items-center justify-between pt-2 flex-wrap gap-3">
          <div className="flex gap-3 flex-wrap">
            <button type="submit" disabled={submitting} className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors">
              {submitting ? "Saving…" : "Save Changes"}
            </button>
            <button type="button" onClick={handleGenerate} disabled={generating} className="border border-[#1E2D45] text-[#8A97B2] rounded-lg py-2 px-4 text-sm hover:text-[#E6EDF7] hover:bg-[#1A2540] disabled:opacity-50 transition-colors">
              {generating ? "Generating…" : "Generate now"}
            </button>
            <a href="/schedules" className="px-5 py-2 text-sm text-[#8A97B2] hover:text-[#E6EDF7] transition-colors">Cancel</a>
          </div>
          <button type="button" onClick={handleDelete} disabled={deleting} className="border border-[#F87171] text-[#F87171] rounded-lg py-2 px-4 text-sm hover:bg-[rgba(248,113,113,0.1)] disabled:opacity-50 transition-colors">
            {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </form>
    </div>
  );
}
