import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Offer } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

// An Offer is named after itself ("New Year 20%"), so the route param arrives
// URL-encoded and must be decoded once before it is used as a docname.
export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const name = decodeId(id);
  const { data, status } = await frappeRequest<{ data: Offer }>(
    `api/resource/Offer/${encodeURIComponent(name)}`,
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}

export async function PUT(req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const name = decodeId(id);
  const body = await req.text();

  const { data, status } = await frappeRequest<{ data: Offer }>(
    `api/resource/Offer/${encodeURIComponent(name)}`,
    { method: "PUT", body, sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}
