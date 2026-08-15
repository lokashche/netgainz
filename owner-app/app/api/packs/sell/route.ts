import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { PackSaleResult } from "@/lib/types";

const SELL = "netgainz.net_gainz.operations.packs.sell_pack";

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await req.text();
  const { data, status } = await frappeRequest<{ message: PackSaleResult }>(
    `api/method/${SELL}`,
    { method: "POST", body, sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
