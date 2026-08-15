import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { ChurnRisk } from "@/lib/types";

const CHURN_RISK = "netgainz.net_gainz.operations.checkin.get_churn_risk";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const threshold = req.nextUrl.searchParams.get("threshold_days");
  const qs = new URLSearchParams();
  if (threshold) qs.set("threshold_days", threshold);

  const { data, status } = await frappeRequest<{ message: ChurnRisk }>(
    `api/method/${CHURN_RISK}?${qs.toString()}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
