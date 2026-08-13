import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { RefundContext, RefundResult } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

/**
 * WP-8 refunds — credit a membership charge, optionally handing the cash back.
 *
 * GET  returns what is still refundable on the current invoice.
 * POST raises the credit note and (when the invoice was actually paid) the
 *      refund Payment Entry. Backend-side that is what makes the refunded rupee
 *      leave the Profit First cash read; nothing here computes money.
 *
 * Owner-only: the backend guards it too, so a Gym Staff session gets a 403 even
 * if it POSTs this route directly.
 */
export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const path =
    "api/method/netgainz.net_gainz.accounting.refunds.get_refund_context" +
    `?membership=${encodeURIComponent(decodeURIComponent(id))}`;

  const { data, status } = await frappeRequest<{ message: RefundContext }>(path, {
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
    payment_mode?: string;
    return_cash?: boolean;
  };

  const amount = Number(body.amount);
  if (!Number.isFinite(amount) || amount <= 0) {
    return NextResponse.json(
      { error: "A refund amount greater than zero is required." },
      { status: 400 }
    );
  }
  // R3 again: the date the money moved is what Profit First reads.
  if (!body.posting_date) {
    return NextResponse.json({ error: "A refund date is required." }, { status: 400 });
  }

  const { data, status } = await frappeRequest<{ message: RefundResult }>(
    "api/method/netgainz.net_gainz.accounting.refunds.refund_membership_payment",
    {
      method: "POST",
      body: JSON.stringify({
        membership: decodeURIComponent(id),
        amount,
        reason: body.reason || undefined,
        posting_date: body.posting_date,
        payment_mode: body.payment_mode || undefined,
        return_cash: body.return_cash === false ? 0 : 1,
      }),
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
