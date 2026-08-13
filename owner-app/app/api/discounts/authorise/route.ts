import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

/**
 * DS-5: the owner approves a bigger discount at the desk with the gym PIN.
 *
 * The PIN is checked by the backend and never stored on the membership — what comes
 * back is a one-time approval that only fits this member, this kind of discount and
 * this size, and expires shortly.
 */
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();

  const { data, status } = await frappeRequest<{ message: { approval: string } }>(
    "api/method/netgainz.net_gainz.accounting.discounts.authorise_discount",
    {
      method: "POST",
      body,
      headers: { "Content-Type": "application/json" },
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
