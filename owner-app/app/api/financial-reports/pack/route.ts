import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { currentBranch } from "@/lib/branchScope";

// Stage 11.5: the accountant pack — one Excel file built by the backend, passed
// through as-is (frappeRequest parses JSON, so this one fetches directly).
export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const sp = req.nextUrl.searchParams;
  const qs = new URLSearchParams({ start: sp.get("from") ?? "", end: sp.get("to") ?? "" });
  const branch = await currentBranch();
  if (branch) qs.set("branch", branch);
  const res = await fetch(
    `${process.env.FRAPPE_URL}/api/method/netgainz.net_gainz.accounting.financial_reports.accountant_pack?${qs}`,
    { headers: { Cookie: session.frappeCookies } }
  );
  if (!res.ok) return NextResponse.json({ error: `Could not build the pack (${res.status})` }, { status: res.status });
  return new NextResponse(await res.arrayBuffer(), {
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": `attachment; filename="accounts-${sp.get("from") ?? ""}-to-${sp.get("to") ?? ""}.xlsx"`,
    },
  });
}
