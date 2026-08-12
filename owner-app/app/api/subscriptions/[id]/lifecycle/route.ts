import { NextRequest, NextResponse } from "next/server";
import { frappeRequest, decodeId } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { FreezeRow } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

/**
 * OP-3 membership lifecycle (ADR-0008).
 *
 * GET  returns the membership's freeze history (newest first).
 * POST dispatches one action — freeze / unfreeze / change-plan / cancel /
 *      transfer — to its whitelisted backend method. The backend owns every
 *      rule: the date-shift arithmetic, the credit math, the tenant's refund
 *      policy, and the owner-only gate on cash leaving.
 */
const METHODS: Record<string, string> = {
  freeze: "netgainz.net_gainz.operations.lifecycle.freeze_membership",
  unfreeze: "netgainz.net_gainz.operations.lifecycle.unfreeze_membership",
  "change-plan": "netgainz.net_gainz.operations.lifecycle.change_plan",
  cancel: "netgainz.net_gainz.operations.lifecycle.cancel_membership",
  transfer: "netgainz.net_gainz.operations.lifecycle.transfer_membership",
};

export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;

  const fields = JSON.stringify(["name", "from_date", "to_date", "days_shifted", "reason"]);
  const filters = JSON.stringify([["membership", "=", decodeId(id)]]);
  const path =
    `api/resource/Membership%20Freeze?fields=${encodeURIComponent(fields)}` +
    `&filters=${encodeURIComponent(filters)}&order_by=${encodeURIComponent("from_date desc")}&limit=20`;

  const { data, status } = await frappeRequest<{ data: FreezeRow[] }>(path, {
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
  const body = (await req.json().catch(() => ({}))) as Record<string, unknown> & {
    action?: string;
  };
  const method = body.action ? METHODS[body.action] : undefined;
  if (!method) {
    return NextResponse.json({ error: "Unknown lifecycle action" }, { status: 400 });
  }

  const args: Record<string, unknown> = { ...body };
  delete args.action;
  // Unfreeze addresses the freeze record itself; everything else the membership.
  if (body.action !== "unfreeze") {
    args.membership = decodeId(id);
  }

  const { data, status } = await frappeRequest<{ message: unknown }>(
    `api/method/${method}`,
    {
      method: "POST",
      body: JSON.stringify(args),
      sessionCookie: session.frappeCookies,
    }
  );
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
