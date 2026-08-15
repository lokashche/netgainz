import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { SetTargetResult } from "@/lib/types";

const SET = "netgainz.net_gainz.operations.assessments.set_target";
const CLEAR = "netgainz.net_gainz.operations.assessments.clear_target";

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await req.text();
  const { data, status } = await frappeRequest<{ message: SetTargetResult }>(
    `api/method/${SET}`,
    { method: "POST", body, sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? data ?? null, { status });
}

export async function DELETE(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const target = req.nextUrl.searchParams.get("target");
  const { data, status } = await frappeRequest<{ message: { target: string } }>(
    `api/method/${CLEAR}`,
    {
      method: "POST",
      body: JSON.stringify({ target }),
      sessionCookie: session.frappeCookies,
    }
  );
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
