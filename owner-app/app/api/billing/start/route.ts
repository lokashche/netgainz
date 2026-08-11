import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { StartBillingResult } from "@/lib/types";

/**
 * Switch automatic billing on for members who were loaded rather than enrolled.
 *
 * Defaults to a **dry run** — the backend changes nothing and reports exactly what
 * it would do. Pass `dry_run: false` to commit.
 *
 * `start_mode` defaults to "Next period", which keeps each member's billing day on
 * their joining anniversary but starts from the next one. Starting on the *current*
 * period would invoice a month most gyms have already collected in cash.
 *
 * Owner-only; enforced server-side too.
 */
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await req.json().catch(() => ({}))) as {
    start_mode?: string;
    dry_run?: boolean;
    memberships?: string[];
  };

  const { data, status } = await frappeRequest<{ message: StartBillingResult }>(
    "api/method/netgainz.net_gainz.accounting.go_live.start_billing",
    {
      method: "POST",
      body: JSON.stringify({
        start_mode: body.start_mode || "Next period",
        dry_run: body.dry_run === false ? 0 : 1,
        memberships: body.memberships,
      }),
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
