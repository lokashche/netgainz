import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

type Params = { params: Promise<{ id: string }> };

/**
 * Raise the current period's invoice now.
 *
 * Used after setting a price on a membership that had none: an unpriced
 * membership is deliberately left without a Subscription — better an obvious gap
 * than a submitted Rs.0 invoice — so billing starts here once a price exists.
 */
export async function POST(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const { data, status } = await frappeRequest<{
    message: { sales_invoice: string | null };
  }>("api/method/netgainz.net_gainz.accounting.billing.generate_membership_invoice", {
    method: "POST",
    body: JSON.stringify({ membership: decodeURIComponent(id) }),
    sessionCookie: session.frappeCookies,
  });

  return NextResponse.json(data, { status });
}
