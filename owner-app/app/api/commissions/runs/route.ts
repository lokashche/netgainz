import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { CoachCommissionRun } from "@/lib/types";

const CREATE =
  "netgainz.net_gainz.doctype.instructor_commission_run.instructor_commission_run.create_commission_run";

// List commission runs (drafts + posted).
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const fields = JSON.stringify([
    "name",
    "period_start",
    "period_end",
    "total_commission",
    "post_to_ledger",
    "journal_entry",
    "docstatus",
  ]);
  const path = `api/resource/Instructor%20Commission%20Run?fields=${encodeURIComponent(fields)}&limit=100&order_by=${encodeURIComponent("period_end desc")}`;

  const { data, status } = await frappeRequest<{ data: CoachCommissionRun[] }>(
    path,
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}

// Create a draft commission run for a period (computes lines; no money moves).
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));
  const qs = new URLSearchParams();
  if (body?.period_start) qs.set("period_start", body.period_start);
  if (body?.period_end) qs.set("period_end", body.period_end);

  const { data, status } = await frappeRequest<{ message: string }>(
    `api/method/${CREATE}?${qs.toString()}`,
    { method: "POST", sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(
    data?.message ? { name: data.message } : data,
    { status }
  );
}
