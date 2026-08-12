import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { PackBalances } from "@/lib/types";

const BALANCES = "netgainz.net_gainz.operations.packs.pack_balances";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const member = req.nextUrl.searchParams.get("member");
  const qs = new URLSearchParams();
  if (member) qs.set("member", member);

  const { data, status } = await frappeRequest<{ message: PackBalances }>(
    `api/method/${BALANCES}?${qs.toString()}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
