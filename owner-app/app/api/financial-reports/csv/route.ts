import { NextRequest, NextResponse } from "next/server";
import { frappeRequest, extractFrappeError } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import { currentBranch } from "@/lib/branchScope";
import { reportPath, type FinancialReport } from "@/lib/financialReports";

// Stage 11.5: the report on screen as a CSV download.
export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const sp = req.nextUrl.searchParams;
  const q = {
    report: sp.get("report") ?? "profit_and_loss",
    from: sp.get("from") ?? "",
    to: sp.get("to") ?? "",
    periodicity: sp.get("periodicity") ?? "Monthly",
  };
  const { data, status } = await frappeRequest<{ message: FinancialReport }>(reportPath(q, await currentBranch()), {
    sessionCookie: session.frappeCookies,
  });
  const r = data?.message;
  if (!r) return NextResponse.json({ error: extractFrappeError(data) ?? "Could not build the report" }, { status });

  const cell = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [r.columns.map((c) => cell(c.label)).join(",")];
  for (const row of r.rows) {
    lines.push(
      r.columns
        .map((c, i) => cell(i === 0 ? "  ".repeat(row._indent) + (row[c.fieldname] ?? "") : row[c.fieldname]))
        .join(",")
    );
  }
  return new NextResponse(lines.join("\n"), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${q.report}-${q.from}-to-${q.to}.csv"`,
    },
  });
}
