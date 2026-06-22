import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { CommissionPreview } from "@/lib/types";

const PREVIEW = "netgainz.net_gainz.operations.commissions.preview_commissions";

// Read-only preview of commission lines for a period (persists nothing).
export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const qs = new URLSearchParams();
  const from = searchParams.get("period_start");
  const to = searchParams.get("period_end");
  if (from) qs.set("period_start", from);
  if (to) qs.set("period_end", to);

  const { data, status } = await frappeRequest<{ message: CommissionPreview }>(
    `api/method/${PREVIEW}?${qs.toString()}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
