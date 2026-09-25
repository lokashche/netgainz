import { extractFrappeError, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { branchParam, currentBranch } from "@/lib/branchScope";
import { redirect } from "next/navigation";

type Row = {
  pack: string;
  sold: number;
  amount: number;
  sessions: number;
  used: number;
  used_pct: number | null;
  active: number;
  expired_unused: number;
  sessions_lost: number;
  value_lost: number;
};

function money(v: number): string {
  return `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

const th = "px-4 py-2 font-medium text-right whitespace-nowrap";
const td = "px-4 py-2 text-right whitespace-nowrap text-[#E6EDF7]";

/**
 * Stage 11.3 — are pack buyers using what they paid for? Packs that expire with
 * sessions left are money in the bank but a member likely not coming back.
 */
export default async function PackReportPage() {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");
  const branch = await currentBranch();
  const { data, status } = await frappeRequest<{ message: { rows: Row[] } }>(
    `api/method/netgainz.net_gainz.operations.packs.get_pack_report?months=12${branchParam(branch)}`,
    { sessionCookie: session.frappeCookies }
  );
  const rows = data?.message?.rows;
  const lost = (rows ?? []).reduce((t, r) => t + r.value_lost, 0);
  const sessionsLost = (rows ?? []).reduce((t, r) => t + r.sessions_lost, 0);

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Pack Usage</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          Packs sold in the last 12 months{branch ? ` · ${branch}` : ""}. A pack that runs out of time with
          sessions left often means a member who stopped coming.
        </p>
      </div>

      {!rows ? (
        <div className="bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm">
          {extractFrappeError(data) ?? `Could not load (${status})`}
        </div>
      ) : (
        <>
          <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl p-5 mb-6">
            <p className="text-[#8A97B2] text-xs uppercase tracking-wider mb-1">Paid for, never used</p>
            <p className={`text-2xl sm:text-3xl font-bold ${lost ? "text-[#FBBF24]" : "text-[#E6EDF7]"}`}>{money(lost)}</p>
            <p className="text-[#8A97B2] text-xs mt-1">{sessionsLost} sessions left on packs that expired</p>
          </div>

          <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wider text-[#8A97B2] border-b border-[#1E2D45]">
                  <th className="px-4 py-2 font-medium text-left">Pack</th>
                  <th className={th}>Sold</th>
                  <th className={th}>Money</th>
                  <th className={th}>Sessions used</th>
                  <th className={th}>Still running</th>
                  <th className={th}>Expired unused</th>
                  <th className={th}>Paid, never used</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-[#8A97B2]">No packs sold in the last 12 months.</td>
                  </tr>
                )}
                {rows.map((r) => (
                  <tr key={r.pack} className="border-b border-[#1E2D45]">
                    <td className="px-4 py-2 text-[#E6EDF7] whitespace-nowrap">{r.pack}</td>
                    <td className={td}>{r.sold}</td>
                    <td className={td}>{money(r.amount)}</td>
                    <td className={td}>
                      {r.used} of {r.sessions}
                      {r.used_pct === null ? "" : ` (${r.used_pct}%)`}
                    </td>
                    <td className={td}>{r.active}</td>
                    <td className={`${td} ${r.expired_unused ? "text-[#FBBF24]" : ""}`}>{r.expired_unused || "—"}</td>
                    <td className={td}>{r.value_lost ? money(r.value_lost) : "—"}</td>
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
