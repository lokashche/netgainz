import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

type Params = { params: Promise<{ id: string }> };

/** DS-2: how an offer is doing — how many members were given it, and how many are left. */
export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const name = decodeId(id);
  const { data, status } = await frappeRequest(
    `api/method/netgainz.net_gainz.accounting.offers.offer_usage?offer=${encodeURIComponent(name)}`,
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}
