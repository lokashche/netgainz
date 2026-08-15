import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { UseSessionResult } from "@/lib/types";

const USE = "netgainz.net_gainz.operations.packs.use_session";

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await req.text();
  const { data, status } = await frappeRequest<{ message: UseSessionResult }>(
    `api/method/${USE}`,
    { method: "POST", body, sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
