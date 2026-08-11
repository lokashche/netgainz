import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { RedeemedCoupon } from "@/lib/types";

/**
 * DS-3: check a coupon code a member has quoted.
 *
 * The backend answers with the offer the code unlocks, or an error saying why it
 * cannot be used. It only checks — the offer is actually given when the membership is
 * saved, where the identical rules run again.
 */
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();

  const { data, status } = await frappeRequest<{ message: RedeemedCoupon }>(
    "api/method/netgainz.net_gainz.accounting.offers.redeem_code",
    {
      method: "POST",
      body,
      headers: { "Content-Type": "application/json" },
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
