import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { RecordAssessmentResult } from "@/lib/types";

const RECORD = "netgainz.net_gainz.operations.assessments.record_assessment";

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await req.text();
  const { data, status } = await frappeRequest<{ message: RecordAssessmentResult }>(
    `api/method/${RECORD}`,
    { method: "POST", body, sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
