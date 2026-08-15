"use client";

// OP-5: the member's measurements and what they add up to.
//
// Every number shown here is computed server-side (BMI, the signed improvement
// deltas, percent-to-target). This panel collects readings and renders what the
// backend says — it never decides whether a change is progress. Which way is
// better is the member's own goal where they have a target (a Weight Gain member
// improves as the number climbs), and the metric's default where they do not.

import { useState, useEffect, useCallback, SyntheticEvent } from "react";
import { extractFrappeError } from "@/lib/frappe";
import type {
  AssessmentMetric,
  MemberProgress,
  MeasurementInput,
  ProgressSeries,
  RecordAssessmentResult,
  SetTargetResult,
} from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const actionBtn =
  "text-xs border border-[#1E2D45] text-[#8A97B2] rounded-lg py-1.5 px-3 hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors";

const primaryBtn =
  "bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors";

function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function fmtNum(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/\.?0+$/, "");
}

/** A signed delta, already oriented so positive means the member improved. */
function Delta({ value, unit }: { value: number | null; unit: string }) {
  if (value === null || value === undefined) return <span className="text-[#8A97B2]">—</span>;
  if (Math.abs(value) < 0.005) return <span className="text-[#8A97B2]">no change</span>;
  const better = value > 0;
  return (
    <span className={better ? "text-[#22D38C]" : "text-[#F87171]"}>
      {better ? "▲" : "▼"} {fmtNum(Math.abs(value))} {unit}
    </span>
  );
}

function TargetBar({ pct }: { pct: number }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-[#1A2540] overflow-hidden">
      <div
        className="h-full rounded-full bg-[#22D38C] transition-[width] duration-500"
        style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
      />
    </div>
  );
}

function SeriesRow({
  series,
  onSetTarget,
  onClearTarget,
  busy,
}: {
  series: ProgressSeries;
  onSetTarget: (metric: string, value: string) => Promise<void>;
  onClearTarget: (target: string) => Promise<void>;
  busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(series.target !== null ? String(series.target) : "");

  return (
    <div className="py-3 border-b border-[#1A2540] last:border-0">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <div className="flex items-baseline gap-2">
          <span className="text-[#E6EDF7] text-sm font-medium">{series.metric}</span>
          <span className="text-[#E6EDF7] text-lg font-bold tabular-nums">
            {fmtNum(series.current)}
          </span>
          <span className="text-[#8A97B2] text-xs">{series.unit}</span>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <span className="text-[#8A97B2]">
            since last <Delta value={series.change_since_last} unit={series.unit} />
          </span>
          <span className="text-[#8A97B2]">
            since first <Delta value={series.change_since_first} unit={series.unit} />
          </span>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-3 flex-wrap">
        {series.target !== null && !editing ? (
          <>
            <div className="flex-1 min-w-[160px]">
              {series.percent_to_target !== null ? (
                <TargetBar pct={series.percent_to_target} />
              ) : (
                <p className="text-xs text-[#8A97B2]">
                  target {fmtNum(series.target)} {series.unit} — no reading yet to measure from
                </p>
              )}
            </div>
            <span className="text-xs text-[#8A97B2] shrink-0">
              target {fmtNum(series.target)} {series.unit}
              {series.percent_to_target !== null && (
                <span className="text-[#22D38C]"> · {fmtNum(series.percent_to_target)}% there</span>
              )}
              {series.target_date ? ` · by ${fmtDate(series.target_date)}` : ""}
            </span>
            <button
              type="button"
              className={actionBtn}
              onClick={() => {
                setDraft(series.target !== null ? String(series.target) : "");
                setEditing(true);
              }}
              disabled={busy}
            >
              Change
            </button>
            <button
              type="button"
              className={actionBtn}
              onClick={() => series.target_name && onClearTarget(series.target_name)}
              disabled={busy}
            >
              Clear
            </button>
          </>
        ) : editing ? (
          <>
            <input
              type="number"
              step="any"
              className={`${inputClass} max-w-[140px]`}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={`Target ${series.unit}`}
            />
            <button
              type="button"
              className={actionBtn}
              disabled={busy || !draft}
              onClick={async () => {
                await onSetTarget(series.metric, draft);
                setEditing(false);
              }}
            >
              Save target
            </button>
            <button type="button" className={actionBtn} onClick={() => setEditing(false)} disabled={busy}>
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            className={actionBtn}
            onClick={() => {
              setDraft(series.target !== null ? String(series.target) : "");
              setEditing(true);
            }}
            disabled={busy}
          >
            Set a target
          </button>
        )}
      </div>

      {series.readings.length > 1 && (
        <p className="mt-2 text-xs text-[#8A97B2] tabular-nums">
          {series.readings
            .slice(-6)
            .map((r) => `${fmtNum(r.value)} (${fmtDate(r.date).slice(0, 6)})`)
            .join("  →  ")}
        </p>
      )}
    </div>
  );
}

export default function ProgressPanel({ memberId }: { memberId: string }) {
  const [progress, setProgress] = useState<MemberProgress | null>(null);
  const [metrics, setMetrics] = useState<AssessmentMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [notes, setNotes] = useState("");
  const [readings, setReadings] = useState<Record<string, string>>({});

  const loadAll = useCallback(async () => {
    try {
      const [progressRes, metricsRes] = await Promise.all([
        fetch(`/api/members/${encodeURIComponent(memberId)}/progress`),
        fetch(`/api/assessments/metrics?member=${encodeURIComponent(memberId)}`),
      ]);
      if (progressRes.ok) {
        setProgress((await progressRes.json()) as MemberProgress | null);
        setLoadFailed(false);
      } else {
        // Never fall through to the empty state: "we could not load this" and
        // "this member has never been measured" must not look the same.
        setLoadFailed(true);
      }
      if (metricsRes.ok) setMetrics(((await metricsRes.json()) as AssessmentMetric[]) ?? []);
    } catch {
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
  }, [memberId]);

  useEffect(() => {
    (async () => {
      await loadAll();
    })();
  }, [loadAll]);

  async function handleRecord(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);

    const measurements: MeasurementInput[] = Object.entries(readings)
      .filter(([, v]) => v !== "")
      .map(([metric, value]) => ({ metric, value }));

    try {
      const res = await fetch("/api/assessments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          member: memberId,
          height_cm: height || null,
          weight_kg: weight || null,
          measurements,
          notes: notes || null,
        }),
      });
      const body = (await res.json().catch(() => null)) as RecordAssessmentResult | null;
      if (!res.ok || !body?.assessment) {
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return;
      }
      setNotice(
        `Assessment recorded${body.bmi ? ` — BMI ${fmtNum(body.bmi)}` : ""}. Next due ${fmtDate(
          body.next_due_date
        )}.`
      );
      // The POST already returns the fresh progress — no second round trip.
      setProgress(body.progress);
      setHeight("");
      setWeight("");
      setNotes("");
      setReadings({});
      setRecording(false);
    } catch {
      setError("Could not reach the server. Nothing was saved — try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSetTarget(metric: string, value: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch("/api/assessments/target", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member: memberId, metric, target_value: value }),
      });
      const body = (await res.json().catch(() => null)) as SetTargetResult | null;
      if (!res.ok || !body?.target) {
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return;
      }
      setNotice(`Target set: ${metric} ${value}.`);
      await loadAll();
    } catch {
      setError("Could not reach the server. The target was not changed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleClearTarget(target: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(`/api/assessments/target?target=${encodeURIComponent(target)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as Record<string, unknown> | null;
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return;
      }
      setNotice("Target cleared. The readings behind it are untouched.");
      await loadAll();
    } catch {
      setError("Could not reach the server. The target was not cleared.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-[#8A97B2] text-sm">Loading…</div>
    );
  }

  const series = progress?.series ?? [];
  const grouped: { label: string; rows: ProgressSeries[] }[] = [
    { label: "Body Composition", rows: series.filter((s) => s.group === "Body Composition") },
    { label: "Performance", rows: series.filter((s) => s.group === "Performance") },
    { label: "Other", rows: series.filter((s) => s.group === "Other") },
  ].filter((g) => g.rows.length > 0);

  return (
    <div className="bg-[#111A2E] rounded-xl border border-[#1E2D45] overflow-hidden mt-6">
      <div className="px-4 py-3 border-b border-[#1E2D45] flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-[#E6EDF7] font-semibold text-sm">Fitness & Progress</p>
          <p className="text-xs text-[#8A97B2] mt-0.5">
            {progress?.assessment_count
              ? `${progress.assessment_count} assessment${
                  progress.assessment_count === 1 ? "" : "s"
                } · last ${fmtDate(progress.last_assessment)}${
                  progress.next_due_date ? ` · next due ${fmtDate(progress.next_due_date)}` : ""
                }`
              : "Not measured yet — the first assessment is the baseline everything else is read against."}
            {progress?.sport_goal ? ` · goal: ${progress.sport_goal}` : ""}
          </p>
        </div>
        <button
          type="button"
          className={actionBtn}
          onClick={() => setRecording((r) => !r)}
          disabled={busy}
        >
          {recording ? "Cancel" : "Record an assessment"}
        </button>
      </div>

      <div className="p-4">
        {error && (
          <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 text-sm text-[#F87171] mb-4">
            {error}
          </div>
        )}
        {notice && (
          <div className="rounded-lg bg-[rgba(34,211,140,0.1)] border border-[#22D38C] px-4 py-3 text-sm text-[#22D38C] mb-4">
            {notice}
          </div>
        )}

        {recording && (
          <form onSubmit={handleRecord} className="mb-6 pb-6 border-b border-[#1E2D45]">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
              <div>
                <label className={labelClass} htmlFor="asm-height">
                  Height (cm)
                </label>
                <input
                  id="asm-height"
                  type="number"
                  step="any"
                  className={inputClass}
                  value={height}
                  onChange={(e) => setHeight(e.target.value)}
                  placeholder="carried forward if blank"
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="asm-weight">
                  Weight (kg)
                </label>
                <input
                  id="asm-weight"
                  type="number"
                  step="any"
                  className={inputClass}
                  value={weight}
                  onChange={(e) => setWeight(e.target.value)}
                />
              </div>
            </div>

            {metrics.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                {metrics.map((m) => (
                  <div key={m.name}>
                    <label className={labelClass} htmlFor={`asm-${m.name}`}>
                      {m.name} ({m.unit})
                    </label>
                    <input
                      id={`asm-${m.name}`}
                      type="number"
                      step="any"
                      className={inputClass}
                      value={readings[m.name] ?? ""}
                      onChange={(e) =>
                        setReadings((prev) => ({ ...prev, [m.name]: e.target.value }))
                      }
                      title={m.description ?? undefined}
                    />
                  </div>
                ))}
              </div>
            )}

            <div className="mb-4">
              <label className={labelClass} htmlFor="asm-notes">
                Coach Notes
              </label>
              <textarea
                id="asm-notes"
                rows={2}
                className={inputClass}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>

            <button type="submit" className={primaryBtn} disabled={busy}>
              {busy ? "Saving…" : "Save assessment"}
            </button>
            <p className="text-xs text-[#8A97B2] mt-2">
              Blank fields are simply not recorded. BMI is calculated for you.
            </p>
          </form>
        )}

        {loadFailed ? (
          <p className="p-8 text-center text-sm text-[#F87171]">
            Could not load this member&apos;s progress. This is not the same as never having
            been measured — reload in a moment.
          </p>
        ) : series.length === 0 ? (
          <p className="p-8 text-center text-sm text-[#8A97B2]">Nothing measured yet.</p>
        ) : (
          grouped.map((g) => (
            <div key={g.label} className="mb-4 last:mb-0">
              <p className="text-xs uppercase tracking-wider text-[#8A97B2] mb-1">{g.label}</p>
              {g.rows.map((s) => (
                <SeriesRow
                  key={s.metric}
                  series={s}
                  onSetTarget={handleSetTarget}
                  onClearTarget={handleClearTarget}
                  busy={busy}
                />
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
