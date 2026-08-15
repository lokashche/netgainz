import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { MembershipPlan } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const q = searchParams.get("q");
  const activeOnly = searchParams.get("active_only") === "1";

  const fields = JSON.stringify([
    "name",
    "plan_name",
    "duration_in_days",
    "amount",
    "is_active",
    "payment_due_rule",
    "installment_count",
    "installment_gap_days",
  ]);

  const filters: Array<[string, string, string | number]> = [];
  if (q) filters.push(["plan_name", "like", `%${q}%`]);
  if (activeOnly) filters.push(["is_active", "=", 1]);

  let path = `api/resource/Membership Plan?fields=${encodeURIComponent(fields)}&limit=50&order_by=${encodeURIComponent("plan_name asc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

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
