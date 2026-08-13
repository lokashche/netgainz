import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { AdvanceContext } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

/**
 * WP-8 money on account — what a member has paid that no invoice has claimed yet.
 *
 * GET  the balance and where it came from.
 * POST take money with no invoice to point it at (paying several months up
 *      front, a joining deposit).
 * PUT  apply what is on account to the member's open dues.
 *
 * Unapplied money is deliberately NOT Profit First revenue: the gym might still
 * have to hand it back. It counts the moment it settles a membership invoice —
 * dated the day it actually arrived, which is why applying an advance can change
 * an earlier period's figures. The backend returns a warning when that happens.
 */
export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const path =
    "api/method/netgainz.net_gainz.accounting.advances.get_advance_context" +
    `?member=${encodeURIComponent(decodeId(id))}`;

  const { data, status } = await frappeRequest<{ message: AdvanceContext }>(path, {
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
    payment_mode?: string;
    posting_date?: string;
    reference_no?: string;
  };

  const amount = Number(body.amount);
  if (!Number.isFinite(amount) || amount <= 0) {
    return NextResponse.json(
      { error: "An amount greater than zero is required." },
      { status: 400 }
    );
  }
  if (!body.posting_date) {
    return NextResponse.json({ error: "A payment date is required." }, { status: 400 });
  }

  const { data, status } = await frappeRequest<{
    message: { payment_entry: string; advance_balance: number };
  }>("api/method/netgainz.net_gainz.accounting.advances.record_member_advance", {
    method: "POST",
    body: JSON.stringify({
      member: decodeId(id),
      amount,
      payment_mode: body.payment_mode || undefined,
      posting_date: body.posting_date,
      reference_no: body.reference_no || undefined,
    }),
    sessionCookie: session.frappeCookies,
  });

  return NextResponse.json(data, { status });
}

export async function PUT(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const { data, status } = await frappeRequest<{
    message: { applied: number; advance_balance: number; warnings: string[] };
  }>("api/method/netgainz.net_gainz.accounting.advances.apply_member_advances", {
    method: "POST",
    body: JSON.stringify({ member: decodeId(id) }),
    sessionCookie: session.frappeCookies,
  });

  return NextResponse.json(data, { status });
}
