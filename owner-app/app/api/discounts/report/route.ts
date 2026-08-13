import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { DiscountsGiven } from "@/lib/types";

/** DS-6: what the gym gave away in a window. Owner-only, enforced server-side. */
export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const args = new URLSearchParams();
  for (const key of ["start", "end", "branch"]) {
    const value = searchParams.get(key);
    if (value) args.set(key, value);
  }

  const { data, status } = await frappeRequest<{ message: DiscountsGiven }>(
    `api/method/netgainz.net_gainz.accounting.discount_report.discounts_given?${args.toString()}`,
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}
