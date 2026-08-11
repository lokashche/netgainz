import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { DiscountPreview } from "@/lib/types";

/**
 * Stage 8 DS-1: what a proposed discount costs, before it is granted.
 *
 * The figures come from the backend (the same helper the invoice uses to price
 * the discount, and the live Profit First percentages) so the preview can never
 * drift from what actually gets billed and allocated.
 */
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();

  const { data, status } = await frappeRequest<{ message: DiscountPreview }>(
    "api/method/netgainz.net_gainz.accounting.discounts.preview_discount",
    {
      method: "POST",
      body,
      headers: { "Content-Type": "application/json" },
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
