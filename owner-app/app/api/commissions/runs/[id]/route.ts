import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { CoachCommissionRun } from "@/lib/types";

const BASE =
  "netgainz.net_gainz.doctype.instructor_commission_run.instructor_commission_run";

// Fetch one run (with its commission lines).
export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await ctx.params;
  const { data, status } = await frappeRequest<{ data: CoachCommissionRun }>(
    `api/resource/Instructor Commission Run/${encodeURIComponent(id)}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}

// Approve (post if posting is enabled) or cancel a run.
export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await ctx.params;
  const body = await req.json().catch(() => ({}));
  const method =
    body?.action === "cancel" ? "cancel_commission_run" : "approve_commission_run";

  const { data, status } = await frappeRequest<{ message: string }>(
    `api/method/${BASE}.${method}?name=${encodeURIComponent(id)}`,
    { method: "POST", sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}

// Discard a draft run.
export async function DELETE(
  _req: NextRequest,
  ctx: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await ctx.params;
  const { data, status } = await frappeRequest<unknown>(
    `api/resource/Instructor Commission Run/${encodeURIComponent(id)}`,
    { method: "DELETE", sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}
