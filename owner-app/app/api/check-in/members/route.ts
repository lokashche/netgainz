import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { CheckinSearchRow } from "@/lib/types";

// OP-1: the desk search is its own server-side read (code / name / phone in one
// query) — the generic /api/members search is name-only.
const FIND = "netgainz.net_gainz.operations.checkin.find_members";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const q = req.nextUrl.searchParams.get("q") ?? "";
  const qs = new URLSearchParams({ q });

  const { data, status } = await frappeRequest<{ message: CheckinSearchRow[] }>(
    `api/method/${FIND}?${qs.toString()}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? [], { status });
}
