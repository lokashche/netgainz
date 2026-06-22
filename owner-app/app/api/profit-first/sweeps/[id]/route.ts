import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { PFSweep } from "@/lib/types";

const BASE = "netgainz.net_gainz.doctype.pf_sweep.pf_sweep";

// Fetch one sweep (with allocations).
export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await ctx.params;
  const { data, status } = await frappeRequest<{ data: PFSweep }>(
    `api/resource/PF Sweep/${encodeURIComponent(id)}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}

// Approve & post, or cancel, a sweep.
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
  const method = body?.action === "cancel" ? "cancel_sweep" : "approve_sweep";

  const { data, status } = await frappeRequest<{ message: string }>(
    `api/method/${BASE}.${method}?name=${encodeURIComponent(id)}`,
    { method: "POST", sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}

// Discard a draft sweep.
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
    `api/resource/PF Sweep/${encodeURIComponent(id)}`,
    { method: "DELETE", sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}
