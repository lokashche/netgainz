"use client";

import type { GapUnit, PaymentDueRule } from "@/lib/types";

// How a member pays: in full, or in parts. The plan carries the gym's usual answer;
// this is where one member gets a different one — the deal struck at the desk.
//
// Shared by the sign-up screen and the membership screen so the two cannot drift
// apart on what the options are or how they are worded.

export const DUE_RULES: PaymentDueRule[] = [
  "On joining",
  "Within 7 days",
  "By the 5th of next month",
];

// "Half now, half next month" is a different promise from "half now, half in 30
// days" — 30 days from the 31st of January is the 2nd of March, and it drifts a
// little further every renewal. Months here mean the calendar month.
export const GAP_UNITS: { value: GapUnit; label: string; one: string }[] = [
  { value: "Days", label: "days", one: "day" },
  { value: "Weeks", label: "weeks", one: "week" },
  { value: "Months", label: "months", one: "month" },
];

export type TermsDraft = {
  /** Empty string means "whatever the plan says". */
  payment_due_rule: PaymentDueRule | "";
  installment_count: number | "";
  installment_gap_days: number | "";
  installment_gap_unit: GapUnit | "";
};

export const EMPTY_TERMS: TermsDraft = {
  payment_due_rule: "",
  installment_count: "",
  installment_gap_days: "",
  installment_gap_unit: "",
};

/** "every month" / "every 4 weeks" / "every 45 days" — mirrors payment_terms.describe_gap. */
export function describeGap(gap: number, unit: GapUnit | ""): string {
  if (!gap || gap < 1) return "";
  const u = GAP_UNITS.find((x) => x.value === (unit || "Days")) ?? GAP_UNITS[0];
  return gap === 1 ? `every ${u.one}` : `every ${gap} ${u.label}`;
}

/** The draft in the gym's own words, so the owner reads a sentence, not a form. */
export function describeTerms(t: TermsDraft, fallback: string): string {
  const parts = Number(t.installment_count || 0);
  if (!parts || parts < 2) {
    if (!t.payment_due_rule) return fallback;
    return `Pays in full ${
      t.payment_due_rule === "On joining"
        ? "when they join"
        : t.payment_due_rule === "Within 7 days"
          ? "within 7 days"
          : "by the 5th of next month"
    }`;
  }
  const gap = Number(t.installment_gap_days || 0);
  const spaced = describeGap(gap, t.installment_gap_unit);
  const every = spaced ? ` ${spaced}` : "";
  const when = t.payment_due_rule
    ? t.payment_due_rule === "On joining"
      ? " starting when they join"
      : t.payment_due_rule === "Within 7 days"
        ? " starting within 7 days"
        : " starting by the 5th of next month"
    : "";
  return `Pays in ${parts} parts${every}${when}`;
}

export default function PaymentTermsFields({
  value,
  onChange,
  planSummary,
  maxInstallments = 12,
  inputClass,
  labelClass,
}: {
  value: TermsDraft;
  onChange: (next: TermsDraft) => void;
  /** What the plan says, shown when nothing is overridden. */
  planSummary: string;
  maxInstallments?: number;
  inputClass: string;
  labelClass: string;
}) {
  const parts = Number(value.installment_count || 0);
  const splitting = parts >= 2;
  const set = (patch: Partial<TermsDraft>) => onChange({ ...value, ...patch });

  return (
    <div className="rounded-lg border border-[#1E2D45] bg-[#111A2E] p-4">
      <div className="flex items-baseline justify-between gap-3 flex-wrap mb-3">
        <h3 className="text-sm font-semibold text-[#E6EDF7]">How they pay</h3>
        <span className="text-xs text-[#8A97B2]">{describeTerms(value, planSummary)}</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className={labelClass} htmlFor="pt-parts">
            Split into
          </label>
          <select
            id="pt-parts"
            value={value.installment_count === "" ? "" : String(value.installment_count)}
            onChange={(e) => {
              const n = e.target.value === "" ? "" : Number(e.target.value);
              // Choosing a split with no gap yet gets the commonest one — a part
              // a month — so the owner never has to know a gap is even required.
              const willSplit = n !== "" && Number(n) >= 2;
              set({
                installment_count: n,
                installment_gap_days:
                  willSplit && value.installment_gap_days === ""
                    ? 1
                    : value.installment_gap_days,
                installment_gap_unit:
                  willSplit && value.installment_gap_unit === ""
                    ? "Months"
                    : value.installment_gap_unit,
              });
            }}
            className={inputClass}
          >
            <option value="">Whatever the plan says</option>
            <option value="1">One payment</option>
            {Array.from({ length: maxInstallments - 1 }, (_, i) => i + 2).map((n) => (
              <option key={n} value={n}>
                {n} parts
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className={labelClass} htmlFor="pt-gap">
            Collect a part every
          </label>
          <div className="flex gap-2">
            <input
              id="pt-gap"
              type="number"
              min={1}
              max={365}
              disabled={!splitting}
              value={value.installment_gap_days === "" ? "" : String(value.installment_gap_days)}
              onChange={(e) =>
                set({ installment_gap_days: e.target.value === "" ? "" : Number(e.target.value) })
              }
              placeholder={splitting ? "1" : "—"}
              className={`${inputClass} disabled:opacity-40 w-20 shrink-0`}
            />
            <select
              id="pt-gap-unit"
              aria-label="Unit"
              disabled={!splitting}
              value={value.installment_gap_unit}
              onChange={(e) =>
                set({ installment_gap_unit: e.target.value as GapUnit | "" })
              }
              className={`${inputClass} disabled:opacity-40`}
            >
              <option value="">Whatever the plan says</option>
              {GAP_UNITS.map((u) => (
                <option key={u.value} value={u.value}>
                  {u.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className={labelClass} htmlFor="pt-due">
            First payment due
          </label>
          <select
            id="pt-due"
            value={value.payment_due_rule}
            onChange={(e) => set({ payment_due_rule: e.target.value as PaymentDueRule | "" })}
            className={inputClass}
          >
            <option value="">Whatever the plan says</option>
            {DUE_RULES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
      </div>

      <p className="text-xs text-[#8A97B2] mt-3">
        Leave these alone and the member follows the plan. Change them and this member
        alone pays differently. <span className="text-[#A9B6CE]">Months</span> means the
        same day next month, so a member who joins on the 31st is never pushed into the
        month after.
      </p>
    </div>
  );
}
