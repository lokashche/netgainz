import { NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { PackAlerts } from "@/lib/types";

const ALERTS = "netgainz.net_gainz.operations.packs.get_pack_alerts_due";

export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: PackAlerts }>(
    `api/method/${ALERTS}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
