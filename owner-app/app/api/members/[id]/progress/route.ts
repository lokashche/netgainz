import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { MemberProgress } from "@/lib/types";

const PROGRESS = "netgainz.net_gainz.operations.assessments.get_progress";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const qs = new URLSearchParams({ member: decodeId(id) });

  const { data, status } = await frappeRequest<{ message: MemberProgress }>(
    `api/method/${PROGRESS}?${qs.toString()}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
