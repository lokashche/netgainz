import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Obligation } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

/**
 * The membership's installment schedule — what is owed and when.
 *
 * Reads the backend's single `open_obligations()` seam, so Commitment mode (one
 * invoice with several scheduled parts) and Pay-as-you-go (one invoice per part)
 * return the same shape and the UI never has to know which is in play.
 */
export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const path =
    "api/method/netgainz.net_gainz.accounting.billing.get_membership_obligations" +
    `?membership=${encodeURIComponent(decodeURIComponent(id))}`;

  const { data, status } = await frappeRequest<{
    message: { obligations: Obligation[]; total: number; outstanding: number };
  }>(path, { sessionCookie: session.frappeCookies });

  return NextResponse.json(data, { status });
}
