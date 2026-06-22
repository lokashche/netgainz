import { NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { PFDashboard } from "@/lib/types";

const DASH = "netgainz.net_gainz.profit_first.dashboard.get_pf_dashboard";

export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: PFDashboard }>(
    `api/method/${DASH}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? { enabled: false }, { status });
}
