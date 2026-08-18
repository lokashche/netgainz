import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Collections } from "@/lib/types";

const READ = "netgainz.net_gainz.accounting.collections.get_collections";

/** Who owes what, and how late — one row per unpaid part, not per member. */
export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const within = req.nextUrl.searchParams.get("within_days");
  const qs = within ? `?within_days=${encodeURIComponent(within)}` : "";

  const { data, status } = await frappeRequest<{ message: Collections }>(
    `api/method/${READ}${qs}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
