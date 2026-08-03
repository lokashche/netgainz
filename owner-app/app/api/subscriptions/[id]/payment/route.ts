import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

type Params = { params: Promise<{ id: string }> };

/**
 * Record a member payment.
 *
 * WP-11: money is recorded ONLY as an ERPNext Payment Entry against the
 * membership's open Sales Invoice — never by writing `fee_collected`, which is a
 * deprecated display field that feeds no calculation. Profit First and instructor
 * commissions read collected cash from Payment Entries, so a payment written the
 * old way would contribute zero revenue.
 */
export async function POST(req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const body = (await req.json()) as {
    amount?: number | string;
    payment_mode?: string;
    posting_date?: string;
    reference_no?: string;
  };

  const amount = Number(body.amount);
  if (!Number.isFinite(amount) || amount <= 0) {
    return NextResponse.json(
      { error: "A payment amount greater than zero is required." },
      { status: 400 }
    );
  }
  // R3: cash counts when it is collected, so the posting date is mandatory.
  if (!body.posting_date) {
    return NextResponse.json(
      { error: "A payment date is required." },
      { status: 400 }
    );
  }

  const { data, status } = await frappeRequest<{
    message: { payment_entry: string; outstanding: number };
  }>("api/method/netgainz.net_gainz.accounting.billing.record_membership_payment", {
    method: "POST",
    body: JSON.stringify({
      membership: decodeURIComponent(id),
      amount,
      payment_mode: body.payment_mode || undefined,
      posting_date: body.posting_date,
      reference_no: body.reference_no || undefined,
    }),
    sessionCookie: session.frappeCookies,
  });

  return NextResponse.json(data, { status });
}
