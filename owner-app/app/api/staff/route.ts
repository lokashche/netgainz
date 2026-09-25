import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { StaffLogin } from "@/lib/types";

const BASE = "netgainz.net_gainz.staff_access";

// Stage 10.4: every gym login, its role and the branches it is limited to.
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: StaffLogin[] }>(
    `api/method/${BASE}.get_staff`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}

// Add a login.
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await req.json().catch(() => ({}));
  const { data, status } = await frappeRequest<{ message: { user: string } }>(
    `api/method/${BASE}.create_staff`,
    {
      method: "POST",
      body: JSON.stringify({
        email: body?.email ?? "",
        full_name: body?.full_name ?? "",
        password: body?.password ?? "",
        role: body?.role ?? "Gym Staff",
        branches: Array.isArray(body?.branches) ? body.branches : [],
      }),
      sessionCookie: session.frappeCookies,
    }
  );
  return NextResponse.json(data, { status });
}
