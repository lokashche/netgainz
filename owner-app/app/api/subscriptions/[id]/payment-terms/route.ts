import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { MembershipTerms } from "@/lib/types";

const GET_TERMS = "netgainz.net_gainz.accounting.payment_terms.get_membership_terms";
const SET_TERMS = "netgainz.net_gainz.accounting.payment_terms.set_membership_terms";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const { data, status } = await frappeRequest<{ message: MembershipTerms }>(
    `api/method/${GET_TERMS}?membership=${encodeURIComponent(decodeId(id))}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}

/** Empty values clear the override and send the member back to the plan's terms. */
export async function POST(req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const body = (await req.json()) as Partial<MembershipTerms>;

  const { data, status } = await frappeRequest<{ message: MembershipTerms }>(
    `api/method/${SET_TERMS}`,
    {
      method: "POST",
      body: JSON.stringify({
        membership: decodeId(id),
        payment_due_rule: body.payment_due_rule ?? "",
        installment_count: body.installment_count ?? 0,
        installment_gap_days: body.installment_gap_days ?? 0,
      }),
      sessionCookie: session.frappeCookies,
    }
  );
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
