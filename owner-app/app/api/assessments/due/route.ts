import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { AssessmentsDue } from "@/lib/types";

const DUE = "netgainz.net_gainz.operations.assessments.get_assessments_due";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const withinDays = req.nextUrl.searchParams.get("within_days");
  const qs = new URLSearchParams();
  if (withinDays) qs.set("within_days", withinDays);

  const { data, status } = await frappeRequest<{ message: AssessmentsDue }>(
    `api/method/${DUE}?${qs.toString()}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
