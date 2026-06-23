import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { ClassSchedule } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const q = searchParams.get("q");
  const activeOnly = searchParams.get("active_only");

  const fields = JSON.stringify([
    "name",
    "title",
    "program",
    "coach",
    "start_time",
    "capacity",
    "on_monday",
    "on_tuesday",
    "on_wednesday",
    "on_thursday",
    "on_friday",
    "on_saturday",
    "on_sunday",
    "is_active",
  ]);

  const filters: string[][] = [];
  if (activeOnly === "1") filters.push(["is_active", "=", "1"]);
  if (q) filters.push(["title", "like", `%${q}%`]);

  let path = `api/resource/Session%20Schedule?fields=${encodeURIComponent(fields)}&limit=100&order_by=${encodeURIComponent("title asc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data, status } = await frappeRequest<{ data: ClassSchedule[] }>(path, {
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

  const { data, status } = await frappeRequest<{ data: ClassSchedule }>(
    "api/resource/Session%20Schedule",
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
