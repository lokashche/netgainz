import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { DayPassSaleResult, TodaysDayPasses } from "@/lib/types";

const TODAYS = "netgainz.net_gainz.operations.packs.todays_day_passes";
const SELL = "netgainz.net_gainz.operations.packs.sell_day_pass";

export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: TodaysDayPasses }>(
    `api/method/${TODAYS}`,
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
  const { data, status } = await frappeRequest<{ message: DayPassSaleResult }>(
    `api/method/${SELL}`,
    { method: "POST", body, sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
