import { extractFrappeError, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { branchParam, currentBranch } from "@/lib/branchScope";
import { redirect } from "next/navigation";
import Link from "next/link";

const BUCKETS = ["Profit", "Owner's Pay", "Tax", "Operating Expenses"] as const;

type Bucket = { cap_pct: number | null; tap_pct: number | null; actual: number };
type PFReports = {
  enabled: boolean;
  trend?: { month: string; real_revenue: number; tier_code: string | null; applicable: boolean; buckets: Record<string, Bucket> }[];
  sweeps?: { name: string; sweep_date: string; period_label: string; real_revenue: number; tier_code: string; status: string; amounts: Record<string, number> }[];
  reserves?: { month: string; balances: Record<string, number> }[];
  tax?: { month: string; set_aside: number; paid: number }[];
};

function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${v < 0 ? "-" : ""}₹${Math.abs(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${Math.round(v)}%`;
}

const th = "px-4 py-2 font-medium text-right whitespace-nowrap";
const td = "px-4 py-2 text-right whitespace-nowrap text-[#E6EDF7]";

function Card({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return (
    <section className="bg-[#111A2E] border border-[#1E2D45] rounded-xl mb-6 overflow-x-auto">
      <div className="px-5 pt-4">
        <p className="text-[#E6EDF7] font-semibold">{title}</p>
        <p className="text-[#8A97B2] text-xs mt-1">{note}</p>
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/**
 * Stage 11.6 — Profit First over time: the month-by-month split against the
 * targets, every sweep, the reserve accounts' balances and tax set aside vs paid.
 */
export default async function PFReportsPage() {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const { data, status } = await frappeRequest<{ message: PFReports }>(
    `api/method/netgainz.net_gainz.profit_first.reports.get_pf_reports?months=12${branchParam(await currentBranch())}`,
    { sessionCookie: session.frappeCookies }
  );
  const r = data?.message;

  return (
    <div>
      <div className="mb-6 flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">Profit First Reports</h1>
          <p className="text-sm text-[#8A97B2] mt-1">The last 12 months — is the money going where Profit First says it should?</p>
        </div>
        <Link href="/profit-first" className="text-sm text-[#5EEAD4] hover:underline">
          ← Profit First
        </Link>
      </div>

      {!r ? (
        <div className="bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm">
          {extractFrappeError(data) ?? `Could not load (${status})`}
        </div>
      ) : !r.enabled ? (
        <p className="text-[#8A97B2] text-sm">Profit First is not switched on yet.</p>
      ) : (
        <>
          <Card
            title="Month by month: actual vs target"
            note="Each bucket's share of Real Revenue that month, against its target. Moving toward the target month after month is the goal."
          >
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wider text-[#8A97B2] border-b border-[#1E2D45]">
                  <th className="px-4 py-2 font-medium text-left">Month</th>
                  <th className={th}>Real Revenue</th>
                  <th className={th}>Health</th>
                  {BUCKETS.map((b) => (
                    <th key={b} className={th}>{b} (target)</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {r.trend?.map((m) => (
                  <tr key={m.month} className="border-b border-[#1E2D45]">
                    <td className="px-4 py-2 text-[#E6EDF7] whitespace-nowrap">{m.month}</td>
                    <td className={td}>{money(m.real_revenue)}</td>
                    <td className={td}>{m.applicable ? m.tier_code ?? "—" : "—"}</td>
                    {BUCKETS.map((b) => (
                      <td key={b} className={td}>
                        {m.applicable ? `${pct(m.buckets[b]?.cap_pct)} (${pct(m.buckets[b]?.tap_pct)})` : "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {r.sweeps && (
            <Card title="Allocations (sweeps)" note="Every time money was set aside into the Profit First accounts.">
              {r.sweeps.length === 0 ? (
                <p className="px-5 pb-4 text-sm text-[#8A97B2]">No sweeps in the last 12 months.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-wider text-[#8A97B2] border-b border-[#1E2D45]">
                      <th className="px-4 py-2 font-medium text-left">Date</th>
                      <th className={th}>Status</th>
                      <th className={th}>Real Revenue</th>
                      {BUCKETS.map((b) => (
                        <th key={b} className={th}>{b}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {r.sweeps.map((s) => (
                      <tr key={s.name} className="border-b border-[#1E2D45]">
                        <td className="px-4 py-2 whitespace-nowrap">
                          <Link href={`/profit-first/sweeps/${encodeURIComponent(s.name)}`} className="text-[#5EEAD4] hover:underline">
                            {s.sweep_date}
                          </Link>
                        </td>
                        <td className={td}>{s.status}</td>
                        <td className={td}>{money(s.real_revenue)}</td>
                        {BUCKETS.map((b) => (
                          <td key={b} className={td}>{money(s.amounts[b])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          )}

          {r.reserves && (
            <Card title="Reserve balances" note="What sits in each Profit First account at each month end.">
              {r.reserves.length === 0 ? (
                <p className="px-5 pb-4 text-sm text-[#8A97B2]">The Profit First accounts are not set up yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-wider text-[#8A97B2] border-b border-[#1E2D45]">
                      <th className="px-4 py-2 font-medium text-left">Month end</th>
                      {BUCKETS.map((b) => (
                        <th key={b} className={th}>{b}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {r.reserves.map((m) => (
                      <tr key={m.month} className="border-b border-[#1E2D45]">
                        <td className="px-4 py-2 text-[#E6EDF7] whitespace-nowrap">{m.month}</td>
                        {BUCKETS.map((b) => (
                          <td key={b} className={td}>{money(m.balances[b])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          )}

          {r.tax && (
            <Card title="Tax: set aside vs paid" note="Tax moved into the Tax account by approved sweeps, against tax actually paid (Tax-bucket expenses).">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs uppercase tracking-wider text-[#8A97B2] border-b border-[#1E2D45]">
                    <th className="px-4 py-2 font-medium text-left">Month</th>
                    <th className={th}>Set aside</th>
                    <th className={th}>Paid</th>
                  </tr>
                </thead>
                <tbody>
                  {r.tax.map((m) => (
                    <tr key={m.month} className="border-b border-[#1E2D45]">
                      <td className="px-4 py-2 text-[#E6EDF7] whitespace-nowrap">{m.month}</td>
                      <td className={td}>{money(m.set_aside)}</td>
                      <td className={td}>{money(m.paid)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
