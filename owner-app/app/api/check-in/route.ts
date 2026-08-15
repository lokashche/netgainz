import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { CheckinResult, TodaysVisits } from "@/lib/types";

const TODAYS_VISITS = "netgainz.net_gainz.operations.checkin.todays_visits";
const RECORD = "netgainz.net_gainz.operations.checkin.record_check_in";

export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data, status } = await frappeRequest<{ message: TodaysVisits }>(
    `api/method/${TODAYS_VISITS}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();

  const { data, status } = await frappeRequest<{ message: CheckinResult }>(
    `api/method/${RECORD}`,
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
