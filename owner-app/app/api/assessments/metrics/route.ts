import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { AssessmentMetric } from "@/lib/types";

const METRICS = "netgainz.net_gainz.operations.assessments.get_metrics";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const member = req.nextUrl.searchParams.get("member");
  const includeInactive = req.nextUrl.searchParams.get("include_inactive");
  const qs = new URLSearchParams();
  if (member) qs.set("member", member);
  if (includeInactive) qs.set("include_inactive", includeInactive);

  const { data, status } = await frappeRequest<{ message: AssessmentMetric[] }>(
    `api/method/${METRICS}?${qs.toString()}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
