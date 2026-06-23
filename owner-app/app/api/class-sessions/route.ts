import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { ClassSession } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const status = searchParams.get("status");
  const coach = searchParams.get("coach");
  const program = searchParams.get("program");
  const q = searchParams.get("q");
  const from = searchParams.get("from");
  const to = searchParams.get("to");

  const fields = JSON.stringify([
    "name",
    "title",
    "program",
    "coach",
    "start_time",
    "duration_mins",
    "capacity",
    "status",
  ]);

  const filters: string[][] = [];
  if (status) filters.push(["status", "=", status]);
  if (coach) filters.push(["coach", "=", coach]);
  if (program) filters.push(["program", "=", program]);
  if (q) filters.push(["title", "like", `%${q}%`]);
  if (from) filters.push(["start_time", ">=", from]);
  if (to) filters.push(["start_time", "<=", to]);

  let path = `api/resource/Session?fields=${encodeURIComponent(fields)}&limit=100&order_by=${encodeURIComponent("start_time desc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data, status: httpStatus } = await frappeRequest<{ data: ClassSession[] }>(
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

  const { data, status: httpStatus } = await frappeRequest<{ data: ClassSession }>(
    "api/resource/Session",
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status: httpStatus });
}
