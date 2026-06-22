import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { RenewalsDue } from "@/lib/types";

const RENEWALS = "netgainz.net_gainz.operations.renewals.get_renewals_due";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const within = searchParams.get("within_days");
  const qs = new URLSearchParams();
  if (within) qs.set("within_days", within);

  const { data, status } = await frappeRequest<{ message: RenewalsDue }>(
    `api/method/${RENEWALS}?${qs.toString()}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
