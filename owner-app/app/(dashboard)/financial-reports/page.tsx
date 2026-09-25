import { extractFrappeError, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { currentBranch } from "@/lib/branchScope";
import { FINANCIAL_REPORTS, reportPath, type FinancialReport } from "@/lib/financialReports";
import { redirect } from "next/navigation";

const inputClass =
  "px-3 py-2.5 rounded-lg text-sm bg-[#1A2540] border border-[#1E2D45] text-[#E6EDF7] focus:outline-none focus:ring-2 focus:ring-[#22D38C]";
const labelClass = "block text-xs uppercase tracking-wider mb-1 text-[#8A97B2]";

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function show(v: string | number | null, fieldtype: string): string {
  if (v === null || v === undefined || v === "") return "";
  if (fieldtype === "Currency" || fieldtype === "Float" || typeof v === "number") {
    const n = Number(v);
    return Number.isFinite(n) ? n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : String(v);
  }
  return String(v);
}

/**
 * Stage 11.5 — the gym's books, from ERPNext's own reports, in plain words.
 * A plain GET form drives it: pick a report and a period, the server draws it.
 * Follows the branch switcher (by cost center). Owner only.
 */
export default async function FinancialReportsPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const session = await getSession();
  if (!session.frappeCookies) redirect("/login");

  const sp = await searchParams;
  const pick = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : "");
  const now = new Date();
  const q = {
    report: pick("report") || "profit_and_loss",
    // Default: the last three months, month by month — comparison built in.
    from: pick("from") || iso(new Date(now.getFullYear(), now.getMonth() - 2, 1)),
    to: pick("to") || iso(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
    periodicity: pick("periodicity") || "Monthly",
  };
  const branch = await currentBranch();
  const { data, status } = await frappeRequest<{ message: FinancialReport }>(reportPath(q, branch), {
    sessionCookie: session.frappeCookies,
  });
  const r = data?.message;
  const meta = FINANCIAL_REPORTS.find((x) => x.key === q.report);
  const qs = new URLSearchParams(q).toString();

  return (
    <div>
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-[#E6EDF7]">Financial Reports</h1>
        <p className="text-sm text-[#8A97B2] mt-1">
          Your official books{branch ? ` · ${branch} only` : ""}. The same figures your accountant sees.
        </p>
      </div>

      <form method="get" className="flex flex-wrap items-end gap-3 mb-5">
        <div>
          <label className={labelClass}>Report</label>
          <select name="report" defaultValue={q.report} className={inputClass}>
            {FINANCIAL_REPORTS.map((x) => (
              <option key={x.key} value={x.key}>
                {x.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass}>From</label>
          <input type="date" name="from" defaultValue={q.from} className={inputClass} />
        </div>
        <div>
          <label className={labelClass}>To</label>
          <input type="date" name="to" defaultValue={q.to} className={inputClass} />
        </div>
        {meta?.periods !== false && (
          <div>
            <label className={labelClass}>Columns</label>
            <select name="periodicity" defaultValue={q.periodicity} className={inputClass}>
              <option value="Monthly">By month</option>
              <option value="Quarterly">By quarter</option>
              <option value="Yearly">By year</option>
            </select>
          </div>
        )}
        <button
          type="submit"
          className="bg-[#22D38C] text-[#0B1220] font-semibold rounded-lg py-2.5 px-5 text-sm hover:bg-[#5EEAD4]"
        >
          Show
        </button>
        <a href={`/api/financial-reports/csv?${qs}`} className="text-sm text-[#5EEAD4] hover:underline py-2.5">
          Download CSV
        </a>
        <a href={`/api/financial-reports/pack?${qs}`} className="text-sm text-[#5EEAD4] hover:underline py-2.5">
          Accountant pack (Excel)
        </a>
      </form>

      {!r ? (
        <div className="bg-[rgba(248,113,113,0.1)] border border-[#F87171] text-[#F87171] rounded-lg p-3 text-sm">
          {extractFrappeError(data) ?? `Could not build the report (${status})`}
        </div>
      ) : (
        <div className="bg-[#111A2E] border border-[#1E2D45] rounded-xl overflow-x-auto">
          <p className="px-5 pt-4 text-[#E6EDF7] font-semibold">{r.title}</p>
          <table className="w-full text-sm mt-2">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wider text-[#8A97B2] border-b border-[#1E2D45]">
                {r.columns.map((c, i) => (
                  <th key={c.fieldname} className={`px-4 py-2 font-medium whitespace-nowrap ${i ? "text-right" : ""}`}>
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.rows.map((row, n) => (
                <tr key={n} className={`border-b border-[#1E2D45] ${row._indent === 0 ? "font-semibold" : ""}`}>
                  {r.columns.map((c, i) => (
                    <td
                      key={c.fieldname}
                      className={`px-4 py-2 text-[#E6EDF7] whitespace-nowrap ${i ? "text-right" : ""}`}
                      style={i === 0 ? { paddingLeft: `${1 + row._indent * 1.25}rem` } : undefined}
                    >
                      {show(row[c.fieldname], c.fieldtype)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
