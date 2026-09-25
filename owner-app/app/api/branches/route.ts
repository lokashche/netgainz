import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Branch } from "@/lib/types";

const BASE = "netgainz.net_gainz.accounting.branch";

// Stage 10.1: every branch, default first, with how many members call it home.
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: Branch[] }>(
    `api/method/${BASE}.get_branches`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}

// Open a new branch. Its accounting cost center is created by the backend.
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await req.json().catch(() => ({}));
  const { data, status } = await frappeRequest<{ message: { name: string } }>(
    `api/method/${BASE}.create_branch`,
    {
      method: "POST",
      body: JSON.stringify({
        branch_name: body?.branch_name ?? "",
        description: body?.description || undefined,
      }),
      sessionCookie: session.frappeCookies,
    }
  );
  return NextResponse.json(data, { status });
}
