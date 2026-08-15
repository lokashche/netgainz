"use client";

// OP-5: the gym's own library of what can be measured.
//
// Every rule here is server-side: a metric with readings behind it cannot be
// deleted or re-united (that would rewrite members' history), and Height /
// Weight / BMI are maintained by the app. This page only collects inputs and
// shows what the backend says.

import { useState, useEffect, useCallback, SyntheticEvent } from "react";
import Link from "next/link";
import { extractFrappeError } from "@/lib/frappe";
import type {
  AssessmentMetric,
  MetricAppliesTo,
  MetricDirection,
  MetricGroup,
} from "@/lib/types";

const inputClass =
  "w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:border-transparent bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] placeholder:text-[#8A97B2] focus:ring-[#22D38C] appearance-none";

const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

const actionBtn =
  "text-xs border border-[#1E2D45] text-[#8A97B2] rounded-lg py-1.5 px-3 hover:text-[#E6EDF7] hover:bg-[#1A2540] transition-colors";

const primaryBtn =
  "bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors";

const GROUPS: MetricGroup[] = ["Body Composition", "Performance", "Other"];
const DIRECTIONS: MetricDirection[] = ["Higher is better", "Lower is better"];
const APPLIES: MetricAppliesTo[] = ["Everyone", "Sport", "General"];

type LibraryMetric = AssessmentMetric & { is_builtin?: 0 | 1 };

export default function MetricLibraryPage() {
  const [metrics, setMetrics] = useState<LibraryMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [edit, setEdit] = useState<Partial<LibraryMetric>>({});

  const [name, setName] = useState("");
  const [unit, setUnit] = useState("");
  const [direction, setDirection] = useState<MetricDirection>("Higher is better");
  const [group, setGroup] = useState<MetricGroup>("Performance");
  const [applies, setApplies] = useState<MetricAppliesTo>("Everyone");
  const [howTo, setHowTo] = useState("");

  const load = useCallback(async () => {
    const res = await fetch("/api/assessment-metrics");
    if (res.ok) {
      const body = (await res.json()) as { data?: LibraryMetric[] };
      setMetrics(body.data ?? []);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    (async () => {
      await load();
    })();
  }, [load]);

  async function handleAdd(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch("/api/assessment-metrics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metric_name: name,
          unit,
          direction,
          metric_group: group,
          applies_to: applies,
          description: howTo || null,
          is_active: 1,
        }),
      });
      const body = (await res.json().catch(() => null)) as { data?: LibraryMetric } | null;
      if (!res.ok || !body?.data?.name) {
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return;
      }
      setNotice(`${name} added. Coaches will see it on the next assessment.`);
      setName("");
      setUnit("");
      setHowTo("");
      setAdding(false);
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(m: LibraryMetric) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(`/api/assessment-metrics/${encodeURIComponent(m.name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          unit: edit.unit,
          direction: edit.direction,
          metric_group: edit.metric_group,
          applies_to: edit.applies_to,
          description: edit.description ?? null,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as Record<string, unknown> | null;
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return;
      }
      setNotice(`${m.name} updated.`);
      setEditing(null);
      await load();
    } catch {
      setError("Could not reach the server. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(m: LibraryMetric) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(`/api/assessment-metrics/${encodeURIComponent(m.name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: m.is_active ? 0 : 1 }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as Record<string, unknown> | null;
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return;
      }
      setNotice(
        m.is_active
          ? `${m.name} switched off. Every reading already taken is kept.`
          : `${m.name} switched back on.`
      );
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function remove(m: LibraryMetric) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(`/api/assessment-metrics/${encodeURIComponent(m.name)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as Record<string, unknown> | null;
        setError(extractFrappeError(body ?? {}) ?? `Error ${res.status}`);
        return;
      }
      setNotice(`${m.name} removed.`);
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-[#8A97B2] text-sm">Loading…</div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">What We Measure</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            The gym&apos;s own list. Add the tests you actually run — a metric tagged Sport only
            appears for Sport members, so a badminton player&apos;s form is not a weight-loss form.
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/assessments" className={actionBtn}>
            ← Assessments
          </Link>
          <button type="button" className={actionBtn} onClick={() => setAdding((a) => !a)}>
            {adding ? "Cancel" : "Add a metric"}
          </button>
        </div>
      </div>

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

      {adding && (
        <form
          onSubmit={handleAdd}
          className="bg-[#111A2E] rounded-xl border border-[#1E2D45] p-6 mb-6"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
            <div>
              <label className={labelClass} htmlFor="m-name">
                Metric
              </label>
              <input
                id="m-name"
                className={inputClass}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Beep Test Level"
                required
              />
            </div>
            <div>
              <label className={labelClass} htmlFor="m-unit">
                Unit
              </label>
              <input
                id="m-unit"
                className={inputClass}
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="sec, cm, %, reps"
                required
              />
            </div>
            <div>
              <label className={labelClass} htmlFor="m-direction">
                Which way is improvement?
              </label>
              <select
                id="m-direction"
                className={inputClass}
                value={direction}
                onChange={(e) => setDirection(e.target.value as MetricDirection)}
              >
                {DIRECTIONS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="m-group">
                Group
              </label>
              <select
                id="m-group"
                className={inputClass}
                value={group}
                onChange={(e) => setGroup(e.target.value as MetricGroup)}
              >
                {GROUPS.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="m-applies">
                Offer it to
              </label>
              <select
                id="m-applies"
                className={inputClass}
                value={applies}
                onChange={(e) => setApplies(e.target.value as MetricAppliesTo)}
              >
                {APPLIES.map((a) => (
                  <option key={a} value={a}>
                    {a === "Everyone" ? "Everyone" : `${a} members only`}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="m-how">
                How to measure (optional)
              </label>
              <input
                id="m-how"
                className={inputClass}
                value={howTo}
                onChange={(e) => setHowTo(e.target.value)}
                placeholder="best of three, full recovery between"
              />
            </div>
          </div>
          <button type="submit" className={primaryBtn} disabled={busy}>
            {busy ? "Adding…" : "Add metric"}
          </button>
          <p className="text-xs text-[#8A97B2] mt-2">
            The unit is fixed once readings exist — changing it later would silently rewrite every
            member&apos;s history.
          </p>
        </form>
      )}

      <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                <th className="text-left font-medium px-4 py-3">Metric</th>
                <th className="text-left font-medium px-4 py-3">Unit</th>
                <th className="text-left font-medium px-4 py-3">Improvement</th>
                <th className="text-left font-medium px-4 py-3">Group</th>
                <th className="text-left font-medium px-4 py-3">Offered To</th>
                <th className="text-right font-medium px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => (
                <tr
                  key={m.name}
                  className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
                >
                  <td className="px-4 py-3">
                    <span className={m.is_active ? "text-[#E6EDF7]" : "text-[#8A97B2] line-through"}>
                      {m.name}
                    </span>
                    {m.is_builtin ? (
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#1A2540] text-[#5EEAD4]">
                        built-in
                      </span>
                    ) : null}
                    {m.description ? (
                      <p className="text-xs text-[#8A97B2] mt-0.5">{m.description}</p>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 text-[#8A97B2]">{m.unit}</td>
                  <td className="px-4 py-3 text-[#8A97B2]">
                    {m.direction === "Higher is better" ? "▲ higher" : "▼ lower"}
                  </td>
                  <td className="px-4 py-3 text-[#8A97B2]">{m.metric_group}</td>
                  <td className="px-4 py-3 text-[#8A97B2]">
                    {m.applies_to === "Everyone" ? "Everyone" : `${m.applies_to} only`}
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    {m.is_builtin ? (
                      <span className="text-xs text-[#8A97B2]">maintained by the app</span>
                    ) : (
                      <>
                        <button
                          type="button"
                          className={actionBtn}
                          onClick={() => {
                            setEdit({ ...m });
                            setEditing(editing === m.name ? null : m.name);
                          }}
                          disabled={busy}
                        >
                          {editing === m.name ? "Close" : "Edit"}
                        </button>
                        <button
                          type="button"
                          className={`${actionBtn} ml-2`}
                          onClick={() => toggleActive(m)}
                          disabled={busy}
                        >
                          {m.is_active ? "Switch off" : "Switch on"}
                        </button>
                        <button
                          type="button"
                          className={`${actionBtn} ml-2`}
                          onClick={() => remove(m)}
                          disabled={busy}
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))
                .flatMap((row, i) => {
                  const m = metrics[i];
                  if (editing !== m.name) return [row];
                  return [
                    row,
                    <tr key={`${m.name}-edit`} className="border-b border-[#1A2540] bg-[#0F1728]">
                      <td colSpan={6} className="px-4 py-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                          <div>
                            <label className={labelClass} htmlFor={`e-unit-${m.name}`}>
                              Unit
                            </label>
                            <input
                              id={`e-unit-${m.name}`}
                              className={inputClass}
                              value={edit.unit ?? ""}
                              onChange={(ev) => setEdit((p) => ({ ...p, unit: ev.target.value }))}
                            />
                          </div>
                          <div>
                            <label className={labelClass} htmlFor={`e-dir-${m.name}`}>
                              Improvement
                            </label>
                            <select
                              id={`e-dir-${m.name}`}
                              className={inputClass}
                              value={edit.direction ?? "Higher is better"}
                              onChange={(ev) =>
                                setEdit((p) => ({ ...p, direction: ev.target.value as MetricDirection }))
                              }
                            >
                              {DIRECTIONS.map((d) => (
                                <option key={d} value={d}>
                                  {d}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className={labelClass} htmlFor={`e-grp-${m.name}`}>
                              Group
                            </label>
                            <select
                              id={`e-grp-${m.name}`}
                              className={inputClass}
                              value={edit.metric_group ?? "Performance"}
                              onChange={(ev) =>
                                setEdit((p) => ({ ...p, metric_group: ev.target.value as MetricGroup }))
                              }
                            >
                              {GROUPS.map((g) => (
                                <option key={g} value={g}>
                                  {g}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className={labelClass} htmlFor={`e-app-${m.name}`}>
                              Offer it to
                            </label>
                            <select
                              id={`e-app-${m.name}`}
                              className={inputClass}
                              value={edit.applies_to ?? "Everyone"}
                              onChange={(ev) =>
                                setEdit((p) => ({ ...p, applies_to: ev.target.value as MetricAppliesTo }))
                              }
                            >
                              {APPLIES.map((a) => (
                                <option key={a} value={a}>
                                  {a === "Everyone" ? "Everyone" : `${a} members only`}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="sm:col-span-2 lg:col-span-4">
                            <label className={labelClass} htmlFor={`e-how-${m.name}`}>
                              How to measure
                            </label>
                            <input
                              id={`e-how-${m.name}`}
                              className={inputClass}
                              value={edit.description ?? ""}
                              onChange={(ev) =>
                                setEdit((p) => ({ ...p, description: ev.target.value }))
                              }
                            />
                          </div>
                        </div>
                        <div className="mt-3 flex items-center gap-2">
                          <button
                            type="button"
                            className={primaryBtn}
                            onClick={() => saveEdit(m)}
                            disabled={busy}
                          >
                            Save changes
                          </button>
                          <span className="text-xs text-[#8A97B2]">
                            The unit is refused once readings exist — that would rewrite history.
                          </span>
                        </div>
                      </td>
                    </tr>,
                  ];
                })}
            </tbody>
          </table>
        </div>
        {metrics.length === 0 && (
          <p className="p-8 text-center text-sm text-[#8A97B2]">
            No metrics yet. Add the first one and coaches can start measuring.
          </p>
        )}
      </div>
    </div>
  );
}
