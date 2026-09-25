import { NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

const BASE = "netgainz.net_gainz.doctype.expense.expense";

// Stage 11.0: how many saved expenses are not in the books yet (owner only).
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: number }>(`api/method/${BASE}.unposted_expense_count`, {
    sessionCookie: session.frappeCookies,
  });
  return NextResponse.json({ count: data?.message ?? 0 }, { status });
}

// Put them in, once.
export async function POST() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: unknown }>(`api/method/${BASE}.post_past_expenses`, {
    method: "POST",
    sessionCookie: session.frappeCookies,
  });
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
