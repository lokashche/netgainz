import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { WriteOffContext } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

/**
 * WP-8 write-offs — give up on dues that will never be collected.
 *
 * Not a refund: the money was earned and billed, it just is not coming. The
 * backend posts a "Write Off Entry" Journal Entry (bad-debt expense against the
 * member's receivable), so no cash moves and Profit First is untouched.
 *
 * Owner-only, enforced server-side as well.
 */
export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const path =
    "api/method/netgainz.net_gainz.accounting.writeoff.get_write_off_context" +
    `?membership=${encodeURIComponent(decodeURIComponent(id))}`;

  const { data, status } = await frappeRequest<{ message: WriteOffContext }>(path, {
    sessionCookie: session.frappeCookies,
  });

  return NextResponse.json(data, { status });
}

export async function POST(req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const body = (await req.json()) as {
    amount?: number | string;
    reason?: string;
    posting_date?: string;
  };

  // Amount is optional — omitted means "everything still outstanding".
  const amount = body.amount === undefined || body.amount === "" ? undefined : Number(body.amount);
  if (amount !== undefined && (!Number.isFinite(amount) || amount <= 0)) {
    return NextResponse.json(
      { error: "The write-off amount must be greater than zero." },
      { status: 400 }
    );
  }

  const { data, status } = await frappeRequest<{
    message: { journal_entry: string; sales_invoice: string; written_off: number };
  }>("api/method/netgainz.net_gainz.accounting.writeoff.write_off_membership_dues", {
    method: "POST",
    body: JSON.stringify({
      membership: decodeURIComponent(id),
      amount,
      reason: body.reason || undefined,
      posting_date: body.posting_date || undefined,
    }),
    sessionCookie: session.frappeCookies,
  });

  return NextResponse.json(data, { status });
}
