"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { extractFrappeError } from "@/lib/frappe";
import type { BillingReadiness, StartBillingResult } from "@/lib/types";

const NEXT_PERIOD = "Next period";
const CURRENT_PERIOD = "Current period";
const CALENDAR_MONTH = "Calendar month";

const card = "bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5";
const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

function formatCurrency(value?: number): string {
  if (value === undefined || value === null) return "—";
  return Number(value).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

const START_OPTIONS = [
  {
    value: NEXT_PERIOD,
    title: "From their next billing date (recommended)",
    blurb:
      "Keeps each member's billing day on their joining anniversary, but starts from the next one. Anything you have already collected in cash stays as it is.",
  },
  {
    value: CALENDAR_MONTH,
    title: "Calendar month — everyone bills 1st to month end",
    blurb:
      "Ignores joining days and puts the whole gym on the same cycle, so each month closes cleanly. Billing starts on the 1st of next month, and the days left in this month are charged once, pro-rata.",
  },
  {
    value: CURRENT_PERIOD,
    title: "Bill the period already in progress",
    blurb:
      "Raises an invoice now for the period each member is currently in. Only choose this if you have NOT collected this period yet — otherwise members get charged twice.",
  },
];

/**
 * The interactive half of Start Billing: choose when billing begins, preview, commit.
 *
 * The readiness list is passed in from the server page. After committing, we ask
 * Next to re-render that server component rather than re-fetching by hand.
 */
export default function StartBillingPanel({ readiness }: { readiness: BillingReadiness }) {
  const router = useRouter();
  const [startMode, setStartMode] = useState(NEXT_PERIOD);
  const [preview, setPreview] = useState<StartBillingResult | null>(null);
  const [committed, setCommitted] = useState<StartBillingResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Empty = the whole gym. A gym can also move members over a few at a time.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [billPartMonth, setBillPartMonth] = useState(true);

  const chosen = selected.size > 0 ? [...selected] : undefined;
  const targetCount = selected.size > 0 ? selected.size : readiness.ready_count;

  function toggle(membership: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(membership)) next.delete(membership);
      else next.add(membership);
      return next;
    });
    setPreview(null);
  }

  async function run(dryRun: boolean) {
    if (!dryRun) {
      const count = preview?.started_count ?? targetCount;
      const when =
        startMode === NEXT_PERIOD ? "their next billing date" : "the period already in progress";
      if (
        !confirm(
          `Start billing for ${count} membership${count === 1 ? "" : "s"}?\n\n` +
            `First invoice: ${when}.\n` +
            "This creates real billing. It cannot be undone in one click."
        )
      ) {
        return;
      }
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/billing/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start_mode: startMode,
          dry_run: dryRun,
          memberships: chosen,
          bill_part_month: billPartMonth,
        }),
      });
      const body = (await res.json().catch(() => ({}))) as { message?: StartBillingResult };
      if (!res.ok) {
        setError(extractFrappeError(body) ?? `Error ${res.status}`);
        return;
      }
      if (dryRun) {
        setPreview(body.message ?? null);
        setCommitted(null);
      } else {
        setCommitted(body.message ?? null);
        setPreview(null);
        setSelected(new Set());
        router.refresh();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const result = committed ?? preview;
  const stats = [
    { label: "Ready", value: readiness.ready_count, tone: "text-[#22D38C]" },
    { label: "Needs a price", value: readiness.blocked_count, tone: "text-[#FBBF24]" },
    { label: "Already billing", value: readiness.already_billing_count, tone: "text-[#8FA3BF]" },
    { label: "With warnings", value: readiness.warning_count, tone: "text-[#5EEAD4]" },
  ];

  return (
    <>
      {error && (
        <div className="rounded-lg bg-[rgba(248,113,113,0.1)] border border-[#F87171] px-4 py-3 mb-6 text-sm text-[#F87171]">
          {error}
        </div>
      )}

      {/* Where things stand */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        {stats.map((stat) => (
          <div key={stat.label} className={card}>
            <p className={labelClass}>{stat.label}</p>
            <p className={`text-2xl font-bold ${stat.tone}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* When should the first invoice land */}
      <div className={`${card} mb-6 space-y-3`}>
        <h2 className="text-sm font-semibold text-[#E5EDF7]">When should billing start?</h2>
        {START_OPTIONS.map((option) => (
          <label
            key={option.value}
            className={`flex gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
              startMode === option.value
                ? "border-[#22D38C] bg-[rgba(34,211,140,0.06)]"
                : "border-[#1E2D45] hover:border-[#2A3D5C]"
            }`}
          >
            <input
              type="radio"
              name="start-mode"
              value={option.value}
              checked={startMode === option.value}
              onChange={() => {
                setStartMode(option.value);
                setPreview(null);
              }}
              className="mt-1 accent-[#22D38C]"
            />
            <span>
              <span className="block text-sm text-[#E6EDF7]">{option.title}</span>
              <span className="block text-xs text-[#8FA3BF] mt-0.5">{option.blurb}</span>
            </span>
          </label>
        ))}

        {startMode === CALENDAR_MONTH && (
          <label className="flex items-center gap-2 text-sm text-[#8FA3BF] pl-1">
            <input
              type="checkbox"
              checked={billPartMonth}
              onChange={(e) => {
                setBillPartMonth(e.target.checked);
                setPreview(null);
              }}
              className="accent-[#22D38C]"
            />
            Also charge the days left in this month (uncheck to let them run free
            until the 1st)
          </label>
        )}

        <div className="flex flex-wrap gap-3 pt-1">
          <button
            type="button"
            onClick={() => run(true)}
            disabled={busy}
            className="border border-[#5EEAD4] text-[#5EEAD4] rounded-lg py-2 px-5 text-sm hover:bg-[rgba(94,234,212,0.1)] disabled:opacity-50 transition-colors"
          >
            {busy ? "Working…" : "Preview"}
          </button>
          <button
            type="button"
            onClick={() => run(false)}
            disabled={busy || !preview || preview.started_count === 0}
            className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2 px-5 text-sm hover:bg-[#5EEAD4] disabled:opacity-50 transition-colors"
          >
            Start billing{selected.size > 0 ? ` (${selected.size} selected)` : ""}
          </button>
          {!preview && !committed && (
            <span className="text-xs text-[#8FA3BF] self-center">
              Preview first — nothing is created until you do.
            </span>
          )}
        </div>
      </div>

      {/* Who to switch on. Leave everything unticked to do the whole gym. */}
      {readiness.ready.length > 0 && (
        <div className={`${card} mb-6`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2 mb-1">
            <h2 className="text-sm font-semibold text-[#E5EDF7]">Ready to bill</h2>
            <span className="text-xs text-[#8FA3BF]">
              {selected.size > 0
                ? `${selected.size} selected`
                : "Nothing ticked — the whole gym will be switched on"}
              {selected.size > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setSelected(new Set());
                    setPreview(null);
                  }}
                  className="ml-3 underline hover:text-[#E6EDF7]"
                >
                  clear
                </button>
              )}
            </span>
          </div>
          <p className="text-sm text-[#8FA3BF] mb-3">
            Tick members to switch on just those — useful for trying it with one
            person first.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[#8FA3BF]">
                  <th className="py-1 pr-3 font-medium w-8"> </th>
                  <th className="py-1 pr-4 font-medium">Member</th>
                  <th className="py-1 pr-4 font-medium text-right">Price</th>
                  <th className="py-1 pr-4 font-medium">First invoice</th>
                  {startMode === CALENDAR_MONTH && billPartMonth && (
                    <th className="py-1 pr-4 font-medium text-right">Rest of this month</th>
                  )}
                  <th className="py-1 font-medium">Note</th>
                </tr>
              </thead>
              <tbody>
                {readiness.ready.map((row) => {
                  const firstInvoice =
                    startMode === CALENDAR_MONTH
                      ? row.calendar_month_start
                      : startMode === CURRENT_PERIOD
                        ? row.current_period_start
                        : row.next_period_start;
                  return (
                    <tr key={row.membership} className="border-t border-[#1E2D45]">
                      <td className="py-2 pr-3">
                        <input
                          type="checkbox"
                          checked={selected.has(row.membership)}
                          onChange={() => toggle(row.membership)}
                          className="accent-[#22D38C]"
                          aria-label={`Select ${row.member_name}`}
                        />
                      </td>
                      <td className="py-2 pr-4 text-[#E6EDF7]">{row.member_name}</td>
                      <td className="py-2 pr-4 text-right">{formatCurrency(row.price)}</td>
                      <td className="py-2 pr-4">{firstInvoice}</td>
                      {startMode === CALENDAR_MONTH && billPartMonth && (
                        <td className="py-2 pr-4 text-right text-[#5EEAD4]">
                          {formatCurrency(row.part_month_amount)}
                          <span className="text-xs text-[#8FA3BF]"> ({row.part_month_days}d)</span>
                        </td>
                      )}
                      <td className="py-2 text-xs text-[#FBBF24]">{row.warnings.join("; ")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* What happened / would happen */}
      {result && (
        <div className={`${card} mb-6`}>
          <h2 className="text-sm font-semibold text-[#E5EDF7] mb-1">
            {result.dry_run ? "Preview" : "Done"}
          </h2>
          <p className="text-sm text-[#8FA3BF] mb-3">
            {result.dry_run
              ? `${result.started_count} membership(s) would start billing. Nothing has been created yet.`
              : `${result.started_count} membership(s) are now billing.`}
            {result.skipped_count > 0 && ` ${result.skipped_count} skipped.`}
            {result.failed_count > 0 && ` ${result.failed_count} failed.`}
            {result.part_month_total > 0 &&
              ` Part-month charges: ${formatCurrency(result.part_month_total)}.`}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[#8FA3BF]">
                  <th className="py-1 pr-4 font-medium">Member</th>
                  <th className="py-1 pr-4 font-medium text-right">Price</th>
                  <th className="py-1 pr-4 font-medium">First invoice</th>
                  <th className="py-1 font-medium">Note</th>
                </tr>
              </thead>
              <tbody>
                {result.started.slice(0, 50).map((row) => (
                  <tr key={row.membership} className="border-t border-[#1E2D45]">
                    <td className="py-2 pr-4 text-[#E6EDF7]">{row.member_name}</td>
                    <td className="py-2 pr-4 text-right">{formatCurrency(row.price)}</td>
                    <td className="py-2 pr-4">{row.first_invoice_on}</td>
                    <td className="py-2 text-xs text-[#FBBF24]">{row.warnings.join("; ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {result.started.length > 50 && (
              <p className="text-xs text-[#8FA3BF] mt-2">
                …and {result.started.length - 50} more.
              </p>
            )}
          </div>
          {result.failed_count > 0 && (
            <ul className="mt-3 text-xs text-[#F87171] space-y-1">
              {result.failed.map((row) => (
                <li key={row.membership}>
                  {row.membership}: {row.error}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* The worklist */}
      {readiness.blocked.length > 0 && (
        <div className={card}>
          <h2 className="text-sm font-semibold text-[#E5EDF7] mb-1">Cannot bill yet</h2>
          <p className="text-sm text-[#8FA3BF] mb-3">
            Fix these and preview again. Most just need a price on the membership.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[#8FA3BF]">
                  <th className="py-1 pr-4 font-medium">Member</th>
                  <th className="py-1 pr-4 font-medium">Plan</th>
                  <th className="py-1 font-medium">Why</th>
                </tr>
              </thead>
              <tbody>
                {readiness.blocked.map((row) => (
                  <tr key={row.membership} className="border-t border-[#1E2D45]">
                    <td className="py-2 pr-4">
                      <a
                        href={`/subscriptions/${encodeURIComponent(row.membership)}`}
                        className="text-[#5EEAD4] hover:underline"
                      >
                        {row.member_name}
                      </a>
                    </td>
                    <td className="py-2 pr-4 text-[#8FA3BF]">{row.membership_plan ?? "—"}</td>
                    <td className="py-2 text-[#FBBF24]">{row.blocked_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
