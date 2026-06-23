import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Coach } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const status = searchParams.get("status");
  const q = searchParams.get("q");

  const fields = JSON.stringify([
    "name",
    "coach_name",
    "phone",
    "email",
    "specialization",
    "commission_type",
    "commission_amount",
    "status",
  ]);

  const filters: string[][] = [];
  if (status) filters.push(["status", "=", status]);
  if (q) filters.push(["coach_name", "like", `%${q}%`]);

  let path = `api/resource/Instructor?fields=${encodeURIComponent(fields)}&limit=50&order_by=${encodeURIComponent("coach_name asc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data, status: httpStatus } = await frappeRequest<{ data: Coach[] }>(
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

  const { data, status: httpStatus } = await frappeRequest<{ data: Coach }>(
    "api/resource/Instructor",
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status: httpStatus });
}
