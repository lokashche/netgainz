import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

const UPDATE = "netgainz.net_gainz.profit_first.schedule.update_pf_schedule";

// Update the sweep schedule (allocation days + auto-create toggle).
export async function PUT(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));
  const params = new URLSearchParams();
  if (body?.allocation_days != null) params.set("allocation_days", String(body.allocation_days));
  if (body?.sweep_auto_create != null)
    params.set("sweep_auto_create", body.sweep_auto_create ? "1" : "0");

  const { data, status } = await frappeRequest<{ message: unknown }>(
    `api/method/${UPDATE}?${params.toString()}`,
    { method: "POST", sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? {}, { status });
}
