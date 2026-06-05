import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { GymSettings } from "@/lib/types";

export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data, status } = await frappeRequest<{ data: GymSettings }>(
    "api/resource/Gym Settings/Gym Settings",
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}

export async function PUT(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();

  const { data, status } = await frappeRequest<{ data: GymSettings }>(
    "api/resource/Gym Settings/Gym Settings",
    {
      method: "PUT",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
