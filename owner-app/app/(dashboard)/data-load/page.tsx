"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  DataLoadProblem,
  DataLoadRunResult,
  DataLoadStep,
  DataLoadValidation,
} from "@/lib/types";

// TL-1 phase 1. Loading a gym's own records used to mean a developer driving
// Frappe Desk. This is that job, done by the owner, in order, with the file
// checked before anything is written.
//
// The order is not cosmetic: the member file names a plan and a programme for
// each person, so those have to exist first or every row fails on a broken link.
// The server enforces it — this screen just makes it obvious.

const CARD = "bg-[#111A2E] border border-[#1E2D45] rounded-xl";
const BTN =
  "px-4 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed";

function statusColour(status: string): string {
  if (status === "Complete") return "#22D38C";
  if (status === "Failed") return "#F87171";
  if (status === "Partial") return "#FBBF24";
  if (status === "Importing") return "#5EEAD4";
  return "#8A97B2";
}

function ProblemList({ problems }: { problems: DataLoadProblem[] }) {
  if (!problems.length) return null;
  return (
    <ul className="mt-3 space-y-2">
      {problems.map((p, i) => {
        const isError = p.kind === "error";
        const colour = isError ? "#F87171" : "#8A97B2";
        return (
          <li
            key={i}
            className="text-sm rounded-lg px-3 py-2"
            style={{
              backgroundColor: isError ? "rgba(248,113,113,0.08)" : "rgba(138,151,178,0.08)",
              color: colour,
            }}
          >
            {p.message}
            {p.rows.length > 0 && (
              <span className="text-[#8A97B2]">
                {" "}
                (line{p.rows.length === 1 ? "" : "s"}{" "}
                {p.rows.slice(0, 12).join(", ")}
                {p.rows.length > 12 ? `, +${p.rows.length - 12} more` : ""})
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function StepCard({
  step,
  index,
  onLoaded,
}: {
  step: DataLoadStep;
  index: number;
  onLoaded: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [content, setContent] = useState("");
  const [checking, setChecking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [check, setCheck] = useState<DataLoadValidation | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const pick = async (f: File | null) => {
    setCheck(null);
    setError("");
    setFile(f);
    setContent(f ? await f.text() : "");
  };

  const post = async (action: "validate" | "run") => {
    const res = await fetch(`/api/data-load?action=${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        step_key: step.key,
        content,
        ...(action === "run" ? { filename: file?.name ?? "" } : {}),
      }),
    });
    if (!res.ok) throw new Error(`That did not work (${res.status}).`);
    return res.json();
  };

  const doCheck = async () => {
    setChecking(true);
    setError("");
    try {
      setCheck((await post("validate")) as DataLoadValidation);
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not work.");
    } finally {
      setChecking(false);
    }
  };

  const doLoad = async () => {
    setLoading(true);
    setError("");
    try {
      const result = (await post("run")) as DataLoadRunResult;
      if (!result.started) {
        setCheck(result.validation);
        setError(result.error ?? "The file was not loaded.");
      } else {
        setFile(null);
        setContent("");
        setCheck(null);
        if (inputRef.current) inputRef.current.value = "";
      }
      onLoaded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not work.");
    } finally {
      setLoading(false);
    }
  };

  const blocked = check ? !check.ok : true;

  return (
    <div className={`${CARD} p-5 mb-4`}>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-[#1E2D45] text-[#8A97B2] text-xs flex items-center justify-center font-semibold">
              {index + 1}
            </span>
            <h2 className="text-[#E6EDF7] font-semibold">{step.label}</h2>
            <span
              className="text-xs px-2 py-0.5 rounded-full"
              style={{
                color: statusColour(step.status),
                backgroundColor: `${statusColour(step.status)}1F`,
              }}
            >
              {step.status}
            </span>
          </div>
          {step.blurb && <p className="text-[#8A97B2] text-sm mt-2">{step.blurb}</p>}
        </div>
        <div className="text-right">
          <p className="text-[#E6EDF7] text-2xl font-bold">{step.loaded}</p>
          <p className="text-[#8A97B2] text-xs">in the system</p>
        </div>
      </div>

      {step.failed_rows ? (
        <div className="mt-3 rounded-lg px-3 py-2 bg-[rgba(251,191,36,0.08)]">
          <p className="text-[#FBBF24] text-sm">
            {step.imported_rows} of {step.total_rows} rows loaded. {step.failed_rows} were
            refused — fix those lines and upload the same file again. What already
            landed is left alone.
          </p>
          <ul className="mt-2 space-y-1">
            {(step.failures ?? []).slice(0, 8).map((f, i) => (
              <li key={i} className="text-[#8A97B2] text-xs">
                line {f.rows}: {f.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {step.message ? <p className="mt-3 text-[#F87171] text-sm">{step.message}</p> : null}

      <div className="mt-4 flex items-center gap-3 flex-wrap">
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
          className="text-sm text-[#8A97B2] file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-[#1E2D45] file:text-[#E6EDF7] hover:file:bg-[#26364F]"
        />
        <button
          type="button"
          onClick={doCheck}
          disabled={!content || checking}
          className={`${BTN} bg-[#1E2D45] text-[#E6EDF7] hover:bg-[#26364F]`}
        >
          {checking ? "Checking…" : "Check the file"}
        </button>
        <button
          type="button"
          onClick={doLoad}
          disabled={blocked || loading}
          className={`${BTN} bg-[#22D38C] text-[#0B1220] hover:bg-[#1CB877]`}
          title={blocked ? "Check the file first" : undefined}
        >
          {loading ? "Loading…" : "Load"}
        </button>
      </div>

      {check && (
        <div className="mt-3">
          <p className="text-sm" style={{ color: check.ok ? "#22D38C" : "#F87171" }}>
            {check.ok
              ? `Ready — ${check.total_rows} rows, nothing wrong with them.`
              : `${check.total_rows} rows read, and this needs fixing first:`}
          </p>
          <ProblemList problems={check.problems} />
        </div>
      )}

      {error && <p className="mt-3 text-[#F87171] text-sm">{error}</p>}
      {step.required_columns?.length ? (
        <p className="mt-3 text-[#8A97B2] text-xs">
          Required columns: {step.required_columns.join(", ")}
        </p>
      ) : null}
    </div>
  );
}

export default function DataLoadPage() {
  const [steps, setSteps] = useState<DataLoadStep[] | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/data-load");
      if (!res.ok) throw new Error(`Could not read the load status (${res.status}).`);
      setSteps((await res.json()) as DataLoadStep[]);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read the load status.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Data Import runs as a background job, so keep polling while one is in flight.
  useEffect(() => {
    if (!steps?.some((s) => s.status === "Importing")) return;
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [steps, refresh]);

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-[#E6EDF7] mb-1">Load your records</h1>
      <p className="text-[#8A97B2] text-sm mb-6">
        Upload the gym&apos;s own lists as CSV files, in this order. Each file is checked
        before anything is written, and uploading the same file twice is safe — rows
        already loaded are left alone.
      </p>

      {error && (
        <div className="mb-4 rounded-lg px-4 py-3 bg-[rgba(248,113,113,0.08)] text-[#F87171] text-sm">
          {error}
        </div>
      )}

      {steps === null && !error ? (
        <p className="text-[#8A97B2] text-sm">Loading…</p>
      ) : (
        steps?.map((s, i) => (
          <StepCard key={s.key} step={s} index={i} onLoaded={refresh} />
        ))
      )}
    </div>
  );
}
