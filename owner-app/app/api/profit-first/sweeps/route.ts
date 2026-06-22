import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { PFSweep } from "@/lib/types";

const CREATE = "netgainz.net_gainz.doctype.pf_sweep.pf_sweep.create_sweep";

// List sweeps (most recent first).
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const fields = JSON.stringify([
    "name",
    "sweep_date",
    "period_label",
    "real_revenue",
    "tier_code",
    "docstatus",
    "journal_entry",
  ]);
  const path = `api/resource/PF Sweep?fields=${encodeURIComponent(
    fields
  )}&order_by=${encodeURIComponent("creation desc")}&limit=50`;

  const { data, status } = await frappeRequest<{ data: PFSweep[] }>(path, {
    sessionCookie: session.frappeCookies,
  });
  return NextResponse.json(data, { status });
}

// Create a draft sweep proposal (no money moves).
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));
  const qs = body?.window ? `?window=${encodeURIComponent(body.window)}` : "";

  const { data, status } = await frappeRequest<{ message: string }>(
    `api/method/${CREATE}${qs}`,
    { method: "POST", sessionCookie: session.frappeCookies }
  );
  return NextResponse.json({ name: data?.message }, { status });
}
