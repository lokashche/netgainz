import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { MembershipPlan } from "@/lib/types";

export async function GET(_req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const fields = JSON.stringify([
    "name",
    "plan_name",
    "duration_in_days",
    "amount",
    "is_active",
  ]);

  const path = `api/resource/Membership Plan?fields=${encodeURIComponent(fields)}&order_by=${encodeURIComponent("plan_name asc")}`;

  const { data, status } = await frappeRequest<{ data: MembershipPlan[] }>(path, {
    sessionCookie: session.frappeCookies,
  });

  return NextResponse.json(data, { status });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();

  const { data, status } = await frappeRequest<{ data: MembershipPlan }>(
    "api/resource/Membership Plan",
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
