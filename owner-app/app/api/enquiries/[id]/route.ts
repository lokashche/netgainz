import { NextRequest, NextResponse } from "next/server";
import { frappeRequest, decodeId } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Enquiry } from "@/lib/types";

type Params = Promise<{ id: string }>;

export async function GET(_req: NextRequest, { params }: { params: Params }) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const { data, status } = await frappeRequest<{ data: Enquiry }>(
    `api/resource/Enquiry/${encodeURIComponent(decodeId(id))}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}

export async function PUT(req: NextRequest, { params }: { params: Params }) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const body = await req.text();
  const { data, status } = await frappeRequest<{ data: Enquiry }>(
    `api/resource/Enquiry/${encodeURIComponent(decodeId(id))}`,
    { method: "PUT", body, sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}

export async function DELETE(_req: NextRequest, { params }: { params: Params }) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const { data, status } = await frappeRequest(
    `api/resource/Enquiry/${encodeURIComponent(decodeId(id))}`,
    { method: "DELETE", sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data ?? {}, { status });
}
