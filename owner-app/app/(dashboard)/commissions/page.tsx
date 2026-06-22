import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { CoachCommissionRun, DocStatus } from "@/lib/types";
import NewRunButton from "./NewRunButton";
import SetupAccountsButton from "./SetupAccountsButton";

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

export default async function CommissionsPage() {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const fields = JSON.stringify([
    "name",
    "period_start",
    "period_end",
    "total_commission",
    "post_to_ledger",
    "journal_entry",
    "docstatus",
  ]);
  const res = await frappeRequest<{ data: CoachCommissionRun[] }>(
    `api/resource/Coach%20Commission%20Run?fields=${encodeURIComponent(
      fields
    )}&order_by=${encodeURIComponent("creation desc")}&limit=50`,
    { sessionCookie: session.frappeCookies }
  );
  const runs: CoachCommissionRun[] = res.data?.data ?? [];

  return (
    <div>
      <div className="mb-6 flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">Coach Commissions</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            Compute each coach&apos;s commission for a period, review it, then approve.
            Posting to the ledger is optional (set in Settings).
          </p>
        </div>
        <div className="flex items-start gap-2">
          <SetupAccountsButton />
          <NewRunButton />
        </div>
      </div>

      <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-hidden">
        {runs.length === 0 ? (
          <div className="p-8 text-center text-[#8A97B2]">
            <p className="text-lg font-medium text-[#E6EDF7]">No commission runs yet</p>
            <p className="text-sm mt-1">
              Create a run to compute each active coach&apos;s commission for a period.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#8A97B2] text-xs uppercase tracking-wider border-b border-[#1E2D45]">
                  <th className="text-left font-medium px-4 py-3">Run</th>
                  <th className="text-left font-medium px-4 py-3">Period</th>
                  <th className="text-right font-medium px-4 py-3">Total</th>
                  <th className="text-left font-medium px-4 py-3">Posting</th>
                  <th className="text-left font-medium px-4 py-3">Journal Entry</th>
                  <th className="text-center font-medium px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const badge = statusBadge(r.docstatus);
                  return (
                    <tr
                      key={r.name}
                      className="border-b border-[#1A2540] last:border-0 hover:bg-[#1A2540] transition-colors"
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={`/commissions/${r.name}`}
                          className="text-[#22D38C] hover:underline font-medium"
                        >
                          {r.name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-[#8A97B2]">
                        {r.period_start ?? "—"} → {r.period_end ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-[#E6EDF7]">
                        {money(r.total_commission)}
                      </td>
                      <td className="px-4 py-3 text-[#8A97B2]">
                        {r.post_to_ledger === 1 ? "Ledger" : "Record-only"}
                      </td>
                      <td className="px-4 py-3 text-[#8A97B2]">
                        {r.journal_entry || "—"}
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
      </div>
    </div>
  );
}
