import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import Link from "next/link";
import { fetchListPage, readPageParams, type SearchParamsObj } from "@/lib/pagination";
import Pagination from "@/app/components/Pagination";
import type { PFSweep, DocStatus, PFDashboard } from "@/lib/types";
import NewSweepButton from "./NewSweepButton";
import SetupAccountsButton from "./SetupAccountsButton";
import ScheduleEditor from "./ScheduleEditor";

type SearchParams = Promise<SearchParamsObj>;

function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `₹${Number(v).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function statusBadge(docstatus: DocStatus) {
  const base =
    "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  if (docstatus === 1)
    return { cls: `${base} bg-[rgba(34,211,140,0.15)] text-[#22D38C]`, label: "Posted" };
  if (docstatus === 2)
    return { cls: `${base} bg-[rgba(248,113,113,0.15)] text-[#F87171]`, label: "Cancelled" };
  return { cls: `${base} bg-[rgba(138,151,178,0.15)] text-[#8A97B2]`, label: "Draft" };
}

export default async function SweepsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const requested = readPageParams(sp);
  const [listResult, dashRes] = await Promise.all([
    fetchListPage<PFSweep>({
      doctype: "PF Sweep",
      fields: [
        "name",
        "sweep_date",
        "period_label",
        "real_revenue",
        "tier_code",
        "docstatus",
        "journal_entry",
      ],
      orderBy: "creation desc",
      sessionCookie: session.frappeCookies,
      ...requested,
    }),
    frappeRequest<{ message: PFDashboard }>(
      `api/method/netgainz.net_gainz.profit_first.dashboard.get_pf_dashboard`,
      { sessionCookie: session.frappeCookies }
    ),
  ]);
  const { rows: sweeps, total, page, pageSize } = listResult;
  const dash = dashRes.data?.message;

  return (
    <div>
      <div className="mb-6 flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-3">
            <Link
              href="/profit-first"
              className="text-sm text-[#8A97B2] hover:text-[#22D38C] transition-colors"
            >
              ← Profit First
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-[#E6EDF7] mt-1">Sweeps</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            Propose a bi-monthly allocation, review it, then approve to post it to
            the ledger. Nothing moves until you approve.
          </p>
        </div>
        <div className="flex items-start gap-2">
          <SetupAccountsButton />
          <NewSweepButton />
        </div>
      </div>

      {dash?.enabled && (
        <div className="mb-5">
          <ScheduleEditor
            allocationDays={dash.allocation_days ?? "10, 25"}
            autoCreate={!!dash.auto_create}
            nextSweepDate={dash.next_sweep_date ?? null}
          />
        </div>
      )}

      <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
        {sweeps.length === 0 ? (
          <div className="p-8 text-center text-[#8A97B2]">
            <p className="text-lg font-medium text-[#E6EDF7]">No sweeps yet</p>
            <p className="text-sm mt-1">
              Create a proposal to see the suggested allocation for this period.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                  <th className="text-left font-medium px-4 py-3">Sweep</th>
                  <th className="text-left font-medium px-4 py-3">Date</th>
                  <th className="text-left font-medium px-4 py-3">Period</th>
                  <th className="text-right font-medium px-4 py-3">Real Revenue</th>
                  <th className="text-center font-medium px-4 py-3">Tier</th>
                  <th className="text-center font-medium px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {sweeps.map((s) => {
                  const badge = statusBadge(s.docstatus);
                  return (
                    <tr
                      key={s.name}
                      className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={`/profit-first/sweeps/${s.name}`}
                          className="text-[#22D38C] hover:underline font-medium"
                        >
                          {s.name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-[#E6EDF7]">{s.sweep_date ?? "—"}</td>
                      <td className="px-4 py-3 text-[#8A97B2]">{s.period_label ?? "—"}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-[#E6EDF7]">
                        {money(s.real_revenue)}
                      </td>
                      <td className="px-4 py-3 text-center text-[#8A97B2]">
                        {s.tier_code ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={badge.cls}>{badge.label}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {total > 0 && (
          <Pagination
            basePath="/profit-first/sweeps"
            searchParams={sp}
            page={page}
            pageSize={pageSize}
            total={total}
            shown={sweeps.length}
            noun="sweeps"
          />
        )}
      </div>
    </div>
  );
}
