"use client";

// OP-2: the pipeline before "Member". Follow-ups due at the top (that is the
// work), then the list by stage, then what each source actually converts.

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import type {
  ConversionBySource,
  Enquiry,
  EnquiryStatus,
  FollowupRow,
  FollowupsDue,
} from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const TABS = ["Open", "New", "Contacted", "Trial Scheduled", "Joined", "Lost", "All"] as const;
type Tab = (typeof TABS)[number];

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

function statusBadge(status: EnquiryStatus): string {
  const base = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "New":
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`;
    case "Contacted":
      return `${base} bg-[rgba(94,234,212,0.15)] text-[#5EEAD4]`;
    case "Trial Scheduled":
      return `${base} bg-[rgba(94,234,212,0.15)] text-[#5EEAD4]`;
    case "Joined":
      return `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`;
    case "Lost":
      return `${base} bg-[rgba(248,113,113,0.15)] text-[#F87171]`;
    default: {
      const _exhaustive: never = status;
      return `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2] /* ${_exhaustive} */`;
    }
  }
}

export default function EnquiriesPage() {
  const [tab, setTab] = useState<Tab>("Open");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Enquiry[]>([]);
  const [loading, setLoading] = useState(true);
  const [followups, setFollowups] = useState<FollowupsDue | null>(null);
  const [conversion, setConversion] = useState<ConversionBySource | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Callers that want a spinner set `loading` themselves (event handlers may;
  // effects may not — the initial state is already loading=true).
  const loadList = useCallback(async (activeTab: Tab, term: string) => {
    try {
      const params = new URLSearchParams();
      if (activeTab !== "All") params.set("status", activeTab);
      if (term) params.set("q", term);
      const res = await fetch(`/api/enquiries?${params.toString()}`);
      if (!res.ok) {
        setRows([]);
        return;
      }
      const body = (await res.json()) as { data?: Enquiry[] };
      setRows(body.data ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadList("Open", "");
    (async () => {
      const res = await fetch("/api/enquiries/followups");
      if (res.ok) setFollowups((await res.json()) as FollowupsDue | null);
    })();
    (async () => {
      const res = await fetch("/api/enquiries/conversion");
      if (res.ok) setConversion((await res.json()) as ConversionBySource | null);
    })();
  }, [loadList]);

  function switchTab(next: Tab) {
    setTab(next);
    setLoading(true);
    loadList(next, q.trim());
  }

  function onSearchChange(value: string) {
    setQ(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setLoading(true);
      loadList(tab, value.trim());
    }, 250);
  }

  const due: FollowupRow[] = [...(followups?.overdue ?? []), ...(followups?.due_today ?? [])];
  const ratedSources = (conversion?.sources ?? []).filter((s) => s.total > 0);

  return (
    <div>
      <div className="flex items-center justify-between flex-wrap gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">Enquiries</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            Everyone who asked — followed up until they join or say why not.
          </p>
        </div>
        <Link
          href="/enquiries/new"
          className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-4 text-sm hover:bg-[#5EEAD4] transition-colors"
        >
          + New Enquiry
        </Link>
      </div>

      {/* Follow-ups due */}
      {due.length > 0 && (
        <div className="mb-6 bg-[rgba(251,191,36,0.05)] border border-[rgba(251,191,36,0.3)] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1E2D45]">
            <h2 className="text-sm font-semibold text-[#FBBF24]">
              Follow-ups due ({due.length})
            </h2>
          </div>
          <ul className="divide-y divide-[#1A2540]">
            {due.map((r) => (
              <li
                key={r.enquiry}
                className="flex items-center justify-between flex-wrap gap-2 px-4 py-2.5 text-sm"
              >
                <div className="min-w-0">
                  <Link
                    href={`/enquiries/${r.enquiry}`}
                    className="text-[#E6EDF7] font-medium hover:text-[#FBBF24]"
                  >
                    {r.full_name}
                  </Link>
                  <span className="text-xs text-[#8A97B2] ml-2">
                    {r.source}
                    {r.phone ? ` · ${r.phone}` : ""}
                  </span>
                </div>
                <span
                  className={`text-xs shrink-0 ${r.days_overdue > 0 ? "text-[#F87171]" : "text-[#FBBF24]"}`}
                >
                  {r.days_overdue > 0 ? `${r.days_overdue}d overdue` : "due today"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* List */}
      <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[#1E2D45] flex items-center gap-2 flex-wrap">
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => switchTab(t)}
              className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                tab === t
                  ? "bg-[#1A2540] text-[#22D38C]"
                  : "text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540]"
              }`}
            >
              {t}
            </button>
          ))}
          <div className="ml-auto w-full sm:w-56">
            <input
              type="text"
              value={q}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search by name…"
              className={inputClass}
            />
          </div>
        </div>

        {loading ? (
          <p className="p-8 text-center text-sm text-[#8A97B2]">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="p-8 text-center text-sm text-[#8A97B2]">
            No enquiries here. Every walk-in and DM belongs on this list.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                  <th className="text-left font-medium px-4 py-3">Name</th>
                  <th className="text-left font-medium px-4 py-3">Phone</th>
                  <th className="hidden md:table-cell text-left font-medium px-4 py-3">Source</th>
                  <th className="hidden md:table-cell text-left font-medium px-4 py-3">Program</th>
                  <th className="text-left font-medium px-4 py-3">Status</th>
                  <th className="text-left font-medium px-4 py-3">Follow-up</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr
                    key={e.name}
                    className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/enquiries/${e.name}`}
                        className="text-[#22D38C] hover:underline font-medium"
                      >
                        {e.full_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-[#8A97B2]">{e.phone || "—"}</td>
                    <td className="hidden md:table-cell px-4 py-3 text-[#8A97B2]">{e.source}</td>
                    <td className="hidden md:table-cell px-4 py-3 text-[#8A97B2]">
                      {e.interested_program || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span className={statusBadge(e.status)}>{e.status}</span>
                    </td>
                    <td className="px-4 py-3 text-[#8A97B2]">{fmtDate(e.next_follow_up)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Conversion by source */}
      {ratedSources.length > 0 && (
        <div className="mt-6 bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#1E2D45]">
            <h2 className="text-sm font-semibold text-[#E6EDF7]">
              What each source converts
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                  <th className="text-left font-medium px-4 py-3">Source</th>
                  <th className="text-right font-medium px-4 py-3">Asked</th>
                  <th className="text-right font-medium px-4 py-3">Joined</th>
                  <th className="text-right font-medium px-4 py-3">Lost</th>
                  <th className="text-right font-medium px-4 py-3">Still open</th>
                  <th className="text-right font-medium px-4 py-3">Conversion</th>
                </tr>
              </thead>
              <tbody>
                {ratedSources.map((s) => (
                  <tr key={s.source} className="border-b border-[#1A2540] last:border-0">
                    <td className="px-4 py-3 text-[#E6EDF7]">{s.source}</td>
                    <td className="px-4 py-3 text-right text-[#8A97B2] tabular-nums">{s.total}</td>
                    <td className="px-4 py-3 text-right text-[#22D38C] tabular-nums">{s.joined}</td>
                    <td className="px-4 py-3 text-right text-[#F87171] tabular-nums">{s.lost}</td>
                    <td className="px-4 py-3 text-right text-[#8A97B2] tabular-nums">{s.open}</td>
                    <td className="px-4 py-3 text-right text-[#E6EDF7] tabular-nums">
                      {s.conversion_pct == null ? "—" : `${s.conversion_pct}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
