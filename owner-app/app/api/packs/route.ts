import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { SessionPack } from "@/lib/types";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const activeOnly = req.nextUrl.searchParams.get("active_only");
  const fields = JSON.stringify([
    "name",
    "pack_name",
    "sessions",
    "validity_days",
    "price",
    "is_active",
    "description",
  ]);
  let path = `api/resource/Session%20Pack?fields=${encodeURIComponent(fields)}&limit=100&order_by=${encodeURIComponent("pack_name asc")}`;
  if (activeOnly) {
    path += `&filters=${encodeURIComponent(JSON.stringify([["is_active", "=", 1]]))}`;
  }

  const { data, status } = await frappeRequest<{ data: SessionPack[] }>(path, {
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
  const { data, status } = await frappeRequest<{ data: SessionPack }>(
    "api/resource/Session%20Pack",
    { method: "POST", body, sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}
