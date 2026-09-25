import { extractFrappeError, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { redirect } from "next/navigation";
import Link from "next/link";

type Row = { branch: string | null; earned: number; spent: number; profit: number };

function fmt(v: number): string {
  return v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function money(v: number): string {
  return v < 0 ? `-₹${fmt(Math.abs(v))}` : `₹${fmt(v)}`;
}

/**
 * Stage 10.5 — earned, spent and profit per branch, from the ledger.
 * Invoiced basis (the books'), so packs, day passes, refunds and expenses all
 * count; the dashboard's "Income this month" is cash received and can differ.
 */
export default async function BranchProfitPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  // Same ?month=<offset> convention as the dashboard (0 = this month).
  const sp = await searchParams;
  const offset = Number(typeof sp.month === "string" ? sp.month : 0) || 0;
  const now = new Date();
  const target = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const mm = String(target.getMonth() + 1).padStart(2, "0");
  const start = `${target.getFullYear()}-${mm}-01`;
  const end = `${target.getFullYear()}-${mm}-${new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate()}`;
  const label = target.toLocaleString("en-US", { month: "long", year: "numeric" });

  const { data, status } = await frappeRequest<{ message: { branches: Row[] } }>(
    `api/method/netgainz.net_gainz.accounting.income_report.get_branch_profit?start=${start}&end=${end}`,
    { sessionCookie: session.frappeCookies }
  );
  const rows = data?.message?.branches ?? [];
  const total = rows.reduce(
    (t, r) => ({ earned: t.earned + r.earned, spent: t.spent + r.spent, profit: t.profit + r.profit }),
    { earned: 0, spent: 0, profit: 0 }
  );

  const tab = (text: string, value: number) => (
    <Link
      key={value}
      href={value ? `/branch-profit?month=${value}` : "/branch-profit"}
      className={
        offset === value
          ? "px-3 py-2.5 sm:py-1.5 text-sm font-semibold rounded-md whitespace-nowrap bg-[#22D38C] text-[#0B1220]"
          : "px-3 py-2.5 sm:py-1.5 text-sm font-medium rounded-md whitespace-nowrap text-[#8A97B2] hover:text-[#E6EDF7]"
      }
    >
      {text}
    </Link>
  );

  const profitClass = (v: number) => (v < 0 ? "text-[#F87171]" : "text-[#22D38C]");

  return (
    <div className="max-w-4xl">
      <div className="mb-6 flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#E6EDF7]">Profit by Branch</h1>
          <p className="text-sm text-[#8A97B2] mt-1">
            {label} · what each branch earned (invoiced) and spent. The dashboard shows cash
            received, so its income can differ.
          </p>
        </div>
        <div className="flex gap-1 bg-[#111A2E] p-1 rounded-lg">
          {tab("This month", 0)}
          {tab("Last month", -1)}
          {tab("2 months ago", -2)}
        </div>
      </div>

      {status !== 200 ? (
        <div className="bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm">
          {extractFrappeError(data) ?? `Could not load (${status})`}
        </div>
      ) : (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wider text-[#8A97B2] border-b border-[#1E2D45]">
                <th className="px-5 py-3 font-medium">Branch</th>
                <th className="px-5 py-3 font-medium text-right">Earned</th>
                <th className="px-5 py-3 font-medium text-right">Spent</th>
                <th className="px-5 py-3 font-medium text-right">Profit</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.branch ?? "-"} className="border-b border-[#1E2D45]">
                  <td className="px-5 py-3 text-[#E6EDF7]">{r.branch ?? "Not tied to a branch"}</td>
                  <td className="px-5 py-3 text-right text-[#E6EDF7]">{money(r.earned)}</td>
                  <td className="px-5 py-3 text-right text-[#E6EDF7]">{money(r.spent)}</td>
                  <td className={`px-5 py-3 text-right font-semibold ${profitClass(r.profit)}`}>{money(r.profit)}</td>
                </tr>
              ))}
              {rows.length > 1 && (
                <tr className="font-semibold">
                  <td className="px-5 py-3 text-[#E6EDF7]">All branches</td>
                  <td className="px-5 py-3 text-right text-[#E6EDF7]">{money(total.earned)}</td>
                  <td className="px-5 py-3 text-right text-[#E6EDF7]">{money(total.spent)}</td>
                  <td className={`px-5 py-3 text-right ${profitClass(total.profit)}`}>{money(total.profit)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
