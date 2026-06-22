import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { InstantAssessment } from "@/lib/types";

// Read-only Profit First Instant Assessment. Proxies the whitelisted Frappe
// method; the gym's session cookie scopes it to their own site (site-per-gym).
export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const window = req.nextUrl.searchParams.get("window");
  const qs = window ? `?window=${encodeURIComponent(window)}` : "";

  const { data, status } = await frappeRequest<{ message: InstantAssessment }>(
    `api/method/netgainz.net_gainz.profit_first.instant_assessment.get_instant_assessment${qs}`,
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data?.message ?? { enabled: false }, { status });
}
