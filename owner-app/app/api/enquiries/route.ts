import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Enquiry } from "@/lib/types";

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
    "full_name",
    "phone",
    "source",
    "interested_program",
    "status",
    "next_follow_up",
    "member",
    "modified",
  ]);

  const filters: (string | string[])[][] = [];
  if (status === "Open") {
    filters.push(["status", "in", ["New", "Contacted", "Trial Scheduled"]]);
  } else if (status) {
    filters.push(["status", "=", status]);
  }
  if (q) filters.push(["full_name", "like", `%${q}%`]);

  let path = `api/resource/Enquiry?fields=${encodeURIComponent(fields)}&limit=100&order_by=${encodeURIComponent("modified desc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data, status: httpStatus } = await frappeRequest<{ data: Enquiry[] }>(
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

  const { data, status: httpStatus } = await frappeRequest<{ data: Enquiry }>(
    "api/resource/Enquiry",
    {
      method: "POST",
      body,
      sessionCookie: session.frappeCookies,
    }
  );
  return NextResponse.json(data, { status: httpStatus });
}
