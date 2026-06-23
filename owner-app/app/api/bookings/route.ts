import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { ClassBooking } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const classSession = searchParams.get("class_session");
  const member = searchParams.get("member");
  const coach = searchParams.get("coach");
  const status = searchParams.get("status");
  const q = searchParams.get("q");

  const fields = JSON.stringify([
    "name",
    "class_session",
    "member",
    "member_name",
    "coach",
    "start_time",
    "status",
    "check_in_time",
  ]);

  const filters: string[][] = [];
  if (classSession) filters.push(["class_session", "=", classSession]);
  if (member) filters.push(["member", "=", member]);
  if (coach) filters.push(["coach", "=", coach]);
  if (status) filters.push(["status", "=", status]);
  if (q) filters.push(["member_name", "like", `%${q}%`]);

  let path = `api/resource/Session%20Booking?fields=${encodeURIComponent(fields)}&limit=100&order_by=${encodeURIComponent("start_time desc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data, status: httpStatus } = await frappeRequest<{ data: ClassBooking[] }>(
    path,
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status: httpStatus });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();

  const { data, status: httpStatus } = await frappeRequest<{ data: ClassBooking }>(
    "api/resource/Session%20Booking",
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status: httpStatus });
}
