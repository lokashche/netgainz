import { NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

const SETUP = "netgainz.net_gainz.profit_first.accounts.setup_profit_first_accounts";

// Idempotently create + map the five Profit First ledger accounts.
export async function POST() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data, status } = await frappeRequest<{ message: unknown }>(
    `api/method/${SETUP}`,
    { method: "POST", sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? {}, { status });
}
