import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { AssessmentRow, InstantAssessment, PFDashboard } from "@/lib/types";

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

const WINDOWS = ["Trailing 12 Months", "This Month"] as const;

// ── formatting helpers ──────────────────────────────────────────────────────

function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const sign = v < 0 ? "-" : "";
  return `${sign}₹${Math.abs(v).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function moneySigned(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const sign = v < 0 ? "-" : "+";
  return `${sign}₹${Math.abs(v).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${v.toFixed(2)}%`;
}

function pctSigned(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const sign = v < 0 ? "-" : "+";
  return `${sign}${Math.abs(v).toFixed(2)}%`;
}

// Underfunding Profit/Owner's Pay/Tax is the concern; OVERspending OpEx is the
// concern. Colour the gap accordingly instead of by raw sign.
function gapColor(row: AssessmentRow): string {
  if (row.gap === null || row.gap === undefined) return "text-[#8A97B2]";
  const attention =
    row.bucket === "Operating Expenses" ? row.gap > 0 : row.gap < 0;
  return attention ? "text-[#F87171]" : "text-[#22D38C]";
}

// ── page ────────────────────────────────────────────────────────────────────

export default async function ProfitFirstPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const requested = typeof sp.window === "string" ? sp.window : "";
  const qs = requested ? `?window=${encodeURIComponent(requested)}` : "";

  const [res, dashRes] = await Promise.all([
    frappeRequest<{ message: InstantAssessment }>(
      `api/method/netgainz.net_gainz.profit_first.instant_assessment.get_instant_assessment${qs}`,
      { sessionCookie: session.frappeCookies }
    ),
    frappeRequest<{ message: PFDashboard }>(
      `api/method/netgainz.net_gainz.profit_first.dashboard.get_pf_dashboard`,
      { sessionCookie: session.frappeCookies }
    ),
  ]);
  const a = res.data?.message;
  const dash = dashRes.data?.message;

  const dashboardStrip = dash?.enabled ? (
    <div className="mb-5 space-y-4">
      {(dash.pending_sweeps?.length ?? 0) > 0 && (
        <Link
          href="/profit-first/sweeps"
          className="block bg-[rgba(245,179,90,0.06)] border border-[rgba(245,179,90,0.3)] rounded-xl p-4 hover:bg-[rgba(245,179,90,0.1)] transition-colors"
        >
          <p className="text-[#F5B35A] text-sm font-medium">
            ⏳ {dash.pending_sweeps!.length} sweep
            {dash.pending_sweeps!.length > 1 ? "s" : ""} awaiting approval — review &amp; post →
          </p>
        </Link>
      )}
      {dash.accounts_ready && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {(dash.reserves ?? []).map((r) => (
            <div
              key={r.role}
              className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-4"
            >
              <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1 truncate">
                {r.role} reserve
              </p>
              <p className="text-[#E6EDF7] text-xl font-bold tabular-nums">
                {money(r.balance)}
              </p>
            </div>
          ))}
        </div>
      )}
      <p className="text-[#8A97B2] text-xs">
        {dash.next_sweep_date ? (
          <>
            Next sweep: <span className="text-[#E6EDF7]">{dash.next_sweep_date}</span> · allocation
            days {dash.allocation_days}
            {dash.auto_create ? " · auto-create on" : ""}
          </>
        ) : (
          <>Allocation days {dash.allocation_days}</>
        )}
      </p>
    </div>
  ) : null;

  const header = (
    <div className="mb-6 flex items-start justify-between flex-wrap gap-3">
      <div>
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Profit First</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          Instant Assessment — where your money actually goes vs. where Profit First
          says it should.
        </p>
      </div>
      <Link
        href="/profit-first/sweeps"
        className="text-sm font-medium px-3 py-2 rounded-lg text-[#E6EDF7] bg-[#1A2540] border border-[#1E2D45] hover:bg-[#22304d] transition-colors whitespace-nowrap"
      >
        Sweeps →
      </Link>
    </div>
  );

  // Not configured / disabled.
  if (!a || !a.enabled) {
    return (
      <div>
        {header}
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-8 text-center">
          <p className="text-[#E6EDF7] text-lg font-medium">
            Profit First isn’t enabled yet
          </p>
          <p className="text-[#8A97B2] text-sm mt-2 max-w-md mx-auto">
            Turn it on and configure your allocation accounts and Real-Revenue
            tier bands in <span className="text-[#E6EDF7]">Profit First Settings</span>{" "}
            (admin), then your Instant Assessment will appear here.
          </p>
        </div>
      </div>
    );
  }

  const effectiveWindow = a.window ?? "Trailing 12 Months";
  const rows = a.rows ?? [];
  const warnings = a.warnings ?? [];
  const breakdown = a.passthrough_breakdown ?? [];

  return (
    <div>
      {header}

      {dashboardStrip}

      {/* Window toggle */}
      <div className="flex items-center gap-2 mb-5">
        {WINDOWS.map((w) => {
          const active = effectiveWindow === w;
          return (
            <a
              key={w}
              href={`/profit-first?window=${encodeURIComponent(w)}`}
              className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                active
                  ? "text-[#E6EDF7] bg-[#1A2540] border border-[#1E2D45]"
                  : "text-[#8A97B2] hover:text-[#E6EDF7] hover:bg-[#1A2540]"
              }`}
            >
              {w}
            </a>
          );
        })}
      </div>

      {/* Real Revenue header card */}
      <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5 mb-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1">
              Real Revenue
            </p>
            <p
              className={`text-3xl font-bold ${
                (a.real_revenue ?? 0) < 0 ? "text-[#F87171]" : "text-[#E6EDF7]"
              }`}
            >
              {money(a.real_revenue)}
            </p>
            <p className="text-[#8A97B2] text-xs mt-1">
              Top-Line {money(a.topline)} − Pass-Through {money(a.passthrough)}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1.5 text-xs">
            <span className="text-[#8A97B2]">
              {a.basis} basis · {a.period_label}
            </span>
            {a.tier_code && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-[rgba(34,211,140,0.12)] text-[#22D38C] font-medium">
                Tier {a.tier_code}
                {a.tier_provisional ? " · provisional" : ""}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Notice (RR ≤ 0 / no tiers) */}
      {a.notice && (
        <div className="bg-[rgba(138,151,178,0.06)] border border-[#1E2D45] rounded-xl p-4 mb-5">
          <p className="text-[#8A97B2] text-sm">{a.notice}</p>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="bg-[rgba(245,179,90,0.06)] border border-[rgba(245,179,90,0.3)] rounded-xl p-4 mb-5 space-y-2">
          {warnings.map((w, i) => (
            <p key={i} className="text-[#F5B35A] text-sm flex gap-2">
              <span aria-hidden="true">⚠</span>
              <span>{w}</span>
            </p>
          ))}
        </div>
      )}

      {/* Assessment table */}
      {a.applicable && rows.length > 0 && (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden mb-5">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                  <th className="text-left font-medium px-4 py-3">Account</th>
                  <th className="text-right font-medium px-4 py-3">Actual ₹</th>
                  <th className="text-right font-medium px-4 py-3">CAP %</th>
                  <th className="text-right font-medium px-4 py-3">TAP %</th>
                  <th className="text-right font-medium px-4 py-3">Target ₹</th>
                  <th className="text-right font-medium px-4 py-3">Gap ₹</th>
                  <th className="text-right font-medium px-4 py-3">Gap %</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.bucket}
                    className="border-b border-[#1A2540] last:border-0"
                  >
                    <td className="px-4 py-3">
                      <span className="text-[#E6EDF7] font-medium">{row.bucket}</span>
                      {row.bucket === "Profit" && (
                        <span className="block text-[#8A97B2] text-xs mt-0.5">
                          Undistributed cash (residual)
                        </span>
                      )}
                    </td>
                    <td
                      className={`px-4 py-3 text-right tabular-nums ${
                        row.actual < 0 ? "text-[#F87171]" : "text-[#E6EDF7]"
                      }`}
                    >
                      {money(row.actual)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-[#8A97B2]">
                      {pct(row.cap_pct)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-[#8A97B2]">
                      {pct(row.tap_pct)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-[#E6EDF7]">
                      {money(row.target)}
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums ${gapColor(row)}`}>
                      {moneySigned(row.gap)}
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums ${gapColor(row)}`}>
                      {pctSigned(row.gap_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pass-through breakdown */}
      {breakdown.length > 0 && (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5 mb-5">
          <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-3">
            Pass-Through excluded from Real Revenue
          </p>
          <ul className="space-y-1.5">
            {breakdown.map((b) => (
              <li
                key={b.category}
                className="flex items-center justify-between text-sm"
              >
                <span className="text-[#E6EDF7] truncate mr-2">{b.category}</span>
                <span className="text-[#8A97B2] tabular-nums shrink-0">
                  {money(b.amount)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-[#8A97B2] text-xs">
        Read-only and advisory. This assessment moves no money and posts no ledger
        entries. The Profit row is a residual (Real Revenue minus recorded
        expenses) and overstates true profit until Owner’s Pay and Tax spend are
        tagged via Expense Category.
      </p>
    </div>
  );
}
