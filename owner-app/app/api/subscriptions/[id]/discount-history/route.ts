import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { DiscountLogRow } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

/** DS-5: every discount decision on this membership — owner-only, enforced server-side. */
export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const name = decodeId(id);
  const { data, status } = await frappeRequest<{ message: DiscountLogRow[] }>(
    `api/method/netgainz.net_gainz.accounting.discounts.discount_history?membership=${encodeURIComponent(name)}`,
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}
