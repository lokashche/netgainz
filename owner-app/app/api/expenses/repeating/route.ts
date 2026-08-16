import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { RepeatingExpenses } from "@/lib/types";

const READ = "netgainz.net_gainz.accounting.recurring.get_repeating";
const RUN = "netgainz.net_gainz.accounting.recurring.run_now";

/** What repeats, and which periods are waiting to be raised. */
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: RepeatingExpenses }>(
    `api/method/${READ}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}

/** Raise the waiting drafts now instead of waiting for tonight. */
export async function POST(_req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{
    message: { created: number; skipped: number };
  }>(`api/method/${RUN}`, {
    method: "POST",
    body: JSON.stringify({}),
    sessionCookie: session.frappeCookies,
  });
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
