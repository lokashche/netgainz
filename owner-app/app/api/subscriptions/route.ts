import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Subscription } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const statusFilter = searchParams.get("status");
  const memberFilter = searchParams.get("member");

  const fields = JSON.stringify([
    "name",
    "member",
    "member_name",
    "membership_plan",
    "month",
    "tariff",
    "fee_collected",
    "balance_due",
    "status",
    "due_date",
  ]);

  const filters: string[][] = [];
  if (statusFilter) filters.push(["status", "=", statusFilter]);
  if (memberFilter) filters.push(["member", "=", memberFilter]);

  let path = `api/resource/Subscription?fields=${encodeURIComponent(fields)}&order_by=${encodeURIComponent("due_date desc")}&limit=100`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data, status } = await frappeRequest<{ data: Subscription[] }>(path, {
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

  const { data, status } = await frappeRequest<{ data: Subscription }>(
    "api/resource/Subscription",
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
