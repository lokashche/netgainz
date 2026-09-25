import { extractFrappeError, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { branchParam, currentBranch } from "@/lib/branchScope";
import { redirect } from "next/navigation";

type Row = {
  month: string;
  active: number;
  joined: number;
  left: number;
  kept_pct: number | null;
  cash: number;
  per_member: number | null;
};
type MemberReport = {
  rows: Row[];
  avg_per_member_month: number | null;
  avg_months_paid: number | null;
  lifetime_value: number | null;
};

function money(v: number | null): string {
  return v === null ? "—" : `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

const th = "px-4 py-2 font-medium text-right whitespace-nowrap";
const td = "px-4 py-2 text-right whitespace-nowrap text-[#E6EDF7]";

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5">
      <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1">{label}</p>
      <p className="text-[#E6EDF7] text-2xl sm:text-3xl font-bold">{value}</p>
      <p className="text-[#8A97B2] text-xs mt-1">{note}</p>
    </div>
  );
}

/**
 * Stage 11.1 — who stayed, who joined, who left, and what a member is worth.
 * "Active" means a paid-for period covers that month (from the invoices; member
 * status records no leave date). Follows the branch switcher (home branch).
 */
export default async function MembersReportPage() {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");
  const branch = await currentBranch();
  const { data, status } = await frappeRequest<{ message: MemberReport }>(
    `api/method/netgainz.net_gainz.accounting.income_report.get_member_report?months=12${branchParam(branch)}`,
    { sessionCookie: session.frappeCookies }
  );
  const r = data?.message;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Members Report</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          The last 12 months{branch ? ` · members of ${branch}` : ""}. A member counts as active in a
          month their payment covers; someone paying late shows as left until they pay.
        </p>
      </div>

      {!r ? (
        <div className="bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm">
          {extractFrappeError(data) ?? `Could not load (${status})`}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <Tile label="Money per member" value={money(r.avg_per_member_month)} note="received per active member, per month" />
            <Tile
              label="Months a member stays"
              value={r.avg_months_paid === null ? "—" : String(r.avg_months_paid)}
              note="average months paid so far"
            />
            <Tile label="Lifetime value" value={money(r.lifetime_value)} note="money per member × months they stay" />
          </div>

          <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wider text-[#8A97B2] border-b border-[#1E2D45]">
                  <th className="px-4 py-2 font-medium text-left">Month</th>
                  <th className={th}>Active</th>
                  <th className={th}>Joined</th>
                  <th className={th}>Left</th>
                  <th className={th}>Kept</th>
                  <th className={th}>Money received</th>
                  <th className={th}>Per member</th>
                </tr>
              </thead>
              <tbody>
                {r.rows.map((m) => (
                  <tr key={m.month} className="border-b border-[#1E2D45]">
                    <td className="px-4 py-2 text-[#E6EDF7] whitespace-nowrap">{m.month}</td>
                    <td className={td}>{m.active}</td>
                    <td className={`${td} text-[#22D38C]`}>{m.joined || "—"}</td>
                    <td className={`${td} ${m.left ? "text-[#F87171]" : ""}`}>{m.left || "—"}</td>
                    <td className={td}>{m.kept_pct === null ? "—" : `${m.kept_pct}%`}</td>
                    <td className={td}>{money(m.cash)}</td>
                    <td className={td}>{money(m.per_member)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
