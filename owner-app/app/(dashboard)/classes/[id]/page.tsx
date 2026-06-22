"use client";

import { useState, useEffect, SyntheticEvent, use, useCallback } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";
import { useClassTerm } from "@/lib/useClassTerm";
import LinkFieldPicker, { type LinkFieldOption } from "@/app/components/LinkFieldPicker";
import type {
  ClassSession,
  ClassSessionStatus,
  ClassBooking,
  ClassBookingStatus,
  Coach,
  Program,
  Member,
} from "@/lib/types";

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

const STATUSES: ClassSessionStatus[] = ["Scheduled", "Completed", "Cancelled"];

type Params = Promise<{ id: string }>;

const toFrappeDT = (v: string) => (v ? v.replace("T", " ") + ":00" : "");

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

function bookingBadge(status: ClassBookingStatus): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "Booked":
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    case "Attended":
      return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
    case "No Show":
      return `${base} bg-[rgba(248,113,113,0.15)] text-[#F87171]`;
    case "Cancelled":
      return `${base} bg-[rgba(248,113,113,0.15)] text-[#F87171]`;
    default: {
      const _exhaustive: never = status;
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2] /* ${_exhaustive} */`;
    }
  }
}

export default function ClassDetailPage({ params }: { params: Params }) {
  const { id } = use(params);
  const router = useRouter();
  const { singular, plural } = useClassTerm();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
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

  // Roster state
  const [bookings, setBookings] = useState<ClassBooking[]>([]);
  const [rosterLoading, setRosterLoading] = useState(true);
  const [rosterError, setRosterError] = useState<string | null>(null);
  const [rosterBusy, setRosterBusy] = useState(false);
  const [newMember, setNewMember] = useState("");
  const [newMemberLabel, setNewMemberLabel] = useState("");
  const [booking, setBooking] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/class-sessions/${encodeURIComponent(id)}`);
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const body = await res.json() as { data?: ClassSession };
        const c = body.data;
        if (!c) throw new Error("Class not found");
        setTitle(c.title ?? "");
        setProgram(c.program ?? "");
        setProgramLabel(c.program ?? "");
        setCoach(c.coach ?? "");
        setCoachLabel(c.coach ?? "");
        setStartTime(c.start_time ? c.start_time.slice(0, 16).replace(" ", "T") : "");
        setDurationMins(c.duration_mins != null ? String(c.duration_mins) : "60");
        setCapacity(c.capacity != null ? String(c.capacity) : "0");
        setStatus(c.status ?? "Scheduled");
        setNotes(c.notes ?? "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load class");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const loadRoster = useCallback(async () => {
    setRosterLoading(true);
    setRosterError(null);
    try {
      const res = await fetch(`/api/bookings?class_session=${encodeURIComponent(id)}`);
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const body = await res.json() as { data?: ClassBooking[] };
      setBookings(body.data ?? []);
    } catch (err) {
      setRosterError(err instanceof Error ? err.message : "Failed to load roster");
    } finally {
      setRosterLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadRoster();
  }, [loadRoster]);

  async function handleSubmit(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(false);

    const payload: Record<string, string | number> = {
      title,
      start_time: toFrappeDT(start_time),
      duration_mins: Number(duration_mins),
      capacity: Number(capacity),
      status,
    };
    payload.program = program;
    payload.coach = coach;
    payload.notes = notes;

    try {
      const res = await fetch(`/api/class-sessions/${encodeURIComponent(id)}`, {
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
    if (!confirm(`Delete class ${id}? This cannot be undone.`)) return;
    setDeleting(true);
    setError(null);

    try {
      const res = await fetch(`/api/class-sessions/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        setDeleting(false);
        return;
      }

      router.push("/classes");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setDeleting(false);
    }
  }

  async function setBookingStatus(b: ClassBooking, next: ClassBookingStatus) {
    setRosterBusy(true);
    setRosterError(null);
    try {
      const res = await fetch(`/api/bookings/${encodeURIComponent(b.name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setRosterError(extractFrappeError(body) ?? `Error ${res.status}`);
        setRosterBusy(false);
        return;
      }
      await loadRoster();
      setRosterBusy(false);
    } catch (err) {
      setRosterError(err instanceof Error ? err.message : "Unexpected error");
      setRosterBusy(false);
    }
  }

  async function bookMember() {
    if (!newMember) return;
    setBooking(true);
    setRosterError(null);
    try {
      const res = await fetch("/api/bookings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ class_session: id, member: newMember }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setRosterError(extractFrappeError(body) ?? `Error ${res.status}`);
        setBooking(false);
        return;
      }
      setNewMember("");
      setNewMemberLabel("");
      await loadRoster();
      setBooking(false);
    } catch (err) {
      setRosterError(err instanceof Error ? err.message : "Unexpected error");
      setBooking(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-[#8A97B2] text-sm">
        Loading…
      </div>
    );
  }

  const cap = Number(capacity);
  // Occupancy must match the server's capacity rule (class_booking.py enforce_capacity),
  // which counts only non-Cancelled bookings. Counting all rows would show a class as
  // full even after a member cancels.
  const bookedCount = bookings.filter((b) => b.status !== "Cancelled").length;
  const bookedLabel = cap > 0 ? `${bookedCount} / ${cap} booked` : `${bookedCount} booked`;

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-4 mb-6">
        <a href="/classes" className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors">
          ← Back to {plural}
        </a>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">
          {singular}{" "}
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
            {singular} updated successfully.
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
              href="/classes"
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
            {deleting ? "Deleting…" : `Delete ${singular}`}
          </button>
        </div>
      </form>

      {/* Roster & Check-in */}
      <div className="mt-6 bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 sm:p-8">
        <div className="flex items-end justify-between flex-wrap gap-3 mb-5">
          <h2 className="text-lg font-bold text-[#E6EDF7]">Roster &amp; Check-in</h2>
          <span className="text-sm text-[#8A97B2] tabular-nums">{bookedLabel}</span>
        </div>

        {rosterError && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171] mb-4">
            {rosterError}
          </div>
        )}

        {rosterLoading ? (
          <p className="text-sm text-[#8A97B2]">Loading roster…</p>
        ) : bookings.length === 0 ? (
          <p className="text-sm text-[#8A97B2]">No members booked yet.</p>
        ) : (
          <ul className="divide-y divide-[#1E2D45]">
            {bookings.map((b) => (
              <li
                key={b.name}
                className="flex items-center justify-between flex-wrap gap-3 py-3"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm text-[#E6EDF7]">
                    {b.member_name ?? b.member}
                  </span>
                  <span className={bookingBadge(b.status)}>{b.status}</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setBookingStatus(b, "Attended")}
                    disabled={rosterBusy || b.status === "Attended"}
                    className="text-xs border border-[#22D38C] text-[#22D38C] rounded-lg py-1.5 px-3 hover:bg-[rgba(34,211,140,0.1)] disabled:opacity-40 transition-colors"
                  >
                    Check in
                  </button>
                  <button
                    type="button"
                    onClick={() => setBookingStatus(b, "No Show")}
                    disabled={rosterBusy || b.status === "No Show"}
                    className="text-xs border border-[#1E2D45] text-[#8A97B2] rounded-lg py-1.5 px-3 hover:text-[#E6EDF7] hover:bg-[#1A2540] disabled:opacity-40 transition-colors"
                  >
                    No show
                  </button>
                  <button
                    type="button"
                    onClick={() => setBookingStatus(b, "Cancelled")}
                    disabled={rosterBusy || b.status === "Cancelled"}
                    className="text-xs border border-[#F87171] text-[#F87171] rounded-lg py-1.5 px-3 hover:bg-[rgba(248,113,113,0.1)] disabled:opacity-40 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {/* Add member */}
        <div className="mt-5 pt-5 border-t border-[#1E2D45]">
          <label className={labelClass}>Add member</label>
          <div className="flex items-start gap-2">
            <div className="flex-1">
              <LinkFieldPicker
                value={newMember}
                displayLabel={newMemberLabel}
                onChange={(id, label) => {
                  setNewMember(id);
                  setNewMemberLabel(label);
                }}
                fetchOptions={fetchMembers}
                placeholder="Search by name…"
                emptyHint="No members found"
                inputClassName={inputClass}
              />
            </div>
            <button
              type="button"
              onClick={bookMember}
              disabled={booking || !newMember}
              className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
            >
              {booking ? "Booking…" : "Book"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
