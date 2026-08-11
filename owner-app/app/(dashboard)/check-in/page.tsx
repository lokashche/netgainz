"use client";

// OP-1: the front-desk screen. Search by name / member code / phone, one tap to
// check a member in, today's visits below. The overdue/frozen prompt is a soft
// banner — a check-in is always recorded, never blocked (D3).

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { extractFrappeError } from "@/lib/frappe";
import type {
  CheckinAlert,
  CheckinResult,
  CheckinSearchRow,
  MemberStatus,
  TodaysVisits,
  VisitRow,
} from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

function fmtTime(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function fmtMoney(value: number): string {
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

function memberBadge(status: MemberStatus): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "Active":
      return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
    case "Frozen":
      return `${base} bg-[rgba(94,234,212,0.15)] text-[#5EEAD4]`;
    case "Inactive":
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    default:
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
  }
}

type Banner = {
  memberName: string;
  member: string;
  alert: CheckinAlert | null;
  previousToday: string | null;
};

export default function CheckInPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<CheckinSearchRow[]>([]);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<Banner | null>(null);

  const [visits, setVisits] = useState<VisitRow[]>([]);
  const [visitsLoading, setVisitsLoading] = useState(true);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchSeqRef = useRef(0);

  const loadVisits = useCallback(async () => {
    try {
      const res = await fetch("/api/check-in");
      if (!res.ok) return;
      const body = (await res.json()) as TodaysVisits | null;
      setVisits(body?.visits ?? []);
    } finally {
      setVisitsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadVisits();
  }, [loadVisits]);

  function onSearchChange(value: string) {
    setQ(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const seq = ++searchSeqRef.current;
    const term = value.trim();
    if (!term) {
      setResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`/api/check-in/members?q=${encodeURIComponent(term)}`);
        if (seq !== searchSeqRef.current) return; // a newer search superseded this one
        if (!res.ok) {
          setResults([]);
          return;
        }
        const body = (await res.json()) as CheckinSearchRow[];
        setResults(body ?? []);
      } finally {
        if (seq === searchSeqRef.current) setSearching(false);
      }
    }, 250);
  }

  async function checkIn(row: CheckinSearchRow) {
    setBusy(true);
    setError(null);
    setBanner(null);
    try {
      const res = await fetch("/api/check-in", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member: row.name }),
      });
      const body = (await res.json().catch(() => null)) as CheckinResult | null;
      if (!res.ok || !body?.check_in) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      setBanner({
        memberName: body.member_name ?? body.member,
        member: body.member,
        alert: body.alert,
        previousToday: body.previous_today,
      });
      setQ("");
      setResults([]);
      await loadVisits();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Check-in</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          Search by name, member code or phone — one tap records the visit.
        </p>
      </div>

      {error && (
        <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171] mb-4">
          {error}
        </div>
      )}

      {banner && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm mb-4 ${
            banner.alert
              ? "bg-[rgba(248,113,113,0.1)] border-[#F87171] text-[#F87171]"
              : "bg-[rgba(34,211,140,0.1)] border-[#22D38C] text-[#22D38C]"
          }`}
        >
          <p className="font-medium">
            {banner.memberName} checked in
            {banner.previousToday
              ? ` — already came in at ${fmtTime(banner.previousToday)} today`
              : ""}
            .
          </p>
          {banner.alert?.overdue && (
            <p className="mt-1">
              ₹{fmtMoney(banner.alert.balance_due)} due
              {banner.alert.due_date ? ` since ${fmtDate(banner.alert.due_date)}` : ""} — a
              good moment to ask for payment.{" "}
              <Link href={`/members/${banner.member}`} className="underline">
                Open member →
              </Link>
            </p>
          )}
          {banner.alert?.frozen && (
            <p className="mt-1">
              This membership is frozen for non-payment — worth a word at the desk.
            </p>
          )}
        </div>
      )}

      {/* Search */}
      <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6">
        <input
          type="text"
          autoFocus
          value={q}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Name, member code or phone…"
          className={inputClass}
        />

        {q.trim() && (
          <div className="mt-4">
            {searching ? (
              <p className="text-sm text-[#8A97B2]">Searching…</p>
            ) : results.length === 0 ? (
              <p className="text-sm text-[#8A97B2]">No members match.</p>
            ) : (
              <ul className="divide-y divide-[#1E2D45]">
                {results.map((r) => (
                  <li
                    key={r.name}
                    className="flex items-center justify-between flex-wrap gap-3 py-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Link
                          href={`/members/${r.name}`}
                          className="text-sm font-medium text-[#E6EDF7] hover:text-[#22D38C] truncate"
                        >
                          {r.full_name}
                        </Link>
                        <span className={memberBadge(r.status)}>{r.status}</span>
                      </div>
                      <p className="text-xs text-[#8A97B2] mt-0.5">
                        <span className="font-mono">{r.name}</span>
                        {r.phone ? ` · ${r.phone}` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {r.checked_in_today && (
                        <span className="text-xs text-[#5EEAD4]">
                          In since {fmtTime(r.checked_in_today)}
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => checkIn(r)}
                        disabled={busy}
                        className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-4 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
                      >
                        {r.checked_in_today ? "Check in again" : "Check in"}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Today's visits */}
      <div className="mt-6 bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden">
        <div className="px-4 py-3 border-b border-[#1E2D45] flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#E6EDF7]">
            Today&apos;s visits ({visits.length})
          </h2>
          <Link href="/churn-risk" className="text-[#5EEAD4] text-xs hover:underline">
            Who hasn&apos;t been coming? →
          </Link>
        </div>
        {visitsLoading ? (
          <p className="p-4 text-sm text-[#8A97B2]">Loading…</p>
        ) : visits.length === 0 ? (
          <p className="p-8 text-center text-sm text-[#8A97B2]">
            No check-ins yet today.
          </p>
        ) : (
          <ul className="divide-y divide-[#1A2540]">
            {visits.map((v) => (
              <li
                key={v.name}
                className="flex items-center justify-between px-4 py-2.5 text-sm"
              >
                <Link
                  href={`/members/${v.member}`}
                  className="text-[#E6EDF7] hover:text-[#22D38C] truncate mr-2"
                >
                  {v.member_name ?? v.member}
                </Link>
                <span className="text-[#8A97B2] text-xs shrink-0 tabular-nums">
                  {fmtTime(v.timestamp)}
                  {v.source && v.source !== "Front Desk" ? ` · ${v.source}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
