import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { AvailableOffer } from "@/lib/types";

/**
 * DS-2: the offers the desk may actually give out right now, for this plan and
 * branch. The backend decides — an offer that has ended, has not started, is out of
 * scope or is used up never reaches the picker, and would be refused on save anyway.
 */
export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const args = new URLSearchParams();
  const plan = searchParams.get("membership_plan");
  const branch = searchParams.get("branch");
  if (plan) args.set("membership_plan", plan);
  if (branch) args.set("branch", branch);

  const { data, status } = await frappeRequest<{ message: AvailableOffer[] }>(
    `api/method/netgainz.net_gainz.accounting.offers.available_offers?${args.toString()}`,
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}
