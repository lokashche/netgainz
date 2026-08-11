import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Offer } from "@/lib/types";

const FIELDS = [
  "name",
  "offer_name",
  "description",
  "discount_type",
  "discount_value",
  "discount_duration",
  "valid_from",
  "valid_upto",
  "max_total_uses",
  "branch",
  "disabled",
];

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = req.nextUrl;
  const q = searchParams.get("q");
  const runningOnly = searchParams.get("running_only");

  const filters: string[][] = [];
  if (runningOnly === "1") filters.push(["disabled", "=", "0"]);
  if (q) filters.push(["offer_name", "like", `%${q}%`]);

  let path = `api/resource/Offer?fields=${encodeURIComponent(JSON.stringify(FIELDS))}&limit=50&order_by=${encodeURIComponent("modified desc")}`;
  if (filters.length > 0) {
    path += `&filters=${encodeURIComponent(JSON.stringify(filters))}`;
  }

  const { data, status } = await frappeRequest<{ data: Offer[] }>(path, {
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

  const { data, status } = await frappeRequest<{ data: Offer }>("api/resource/Offer", {
    method: "POST",
    body,
    sessionCookie: session.frappeCookies,
  });

  return NextResponse.json(data, { status });
}
