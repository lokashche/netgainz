import { NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { FollowupsDue } from "@/lib/types";

const FOLLOWUPS = "netgainz.net_gainz.operations.enquiries.get_followups_due";

export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: FollowupsDue }>(
    `api/method/${FOLLOWUPS}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
