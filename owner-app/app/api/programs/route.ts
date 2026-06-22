import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Program } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const q = searchParams.get("q");
  const activeOnly = searchParams.get("active_only");

  const fields = JSON.stringify(["name", "program_name", "description", "is_active"]);

  const filters: string[][] = [];
  if (activeOnly === "1") filters.push(["is_active", "=", "1"]);
  if (q) filters.push(["program_name", "like", `%${q}%`]);

  let path = `api/resource/Program?fields=${encodeURIComponent(fields)}&limit=50&order_by=${encodeURIComponent("program_name asc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data, status: httpStatus } = await frappeRequest<{ data: Program[] }>(
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

  const { data, status: httpStatus } = await frappeRequest<{ data: Program }>(
    "api/resource/Program",
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status: httpStatus });
}
