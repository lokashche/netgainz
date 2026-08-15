import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { AssessmentMetric } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

export async function PUT(req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const body = await req.text();
  const { data, status } = await frappeRequest<{ data: AssessmentMetric }>(
    `api/resource/Assessment Metric/${encodeURIComponent(decodeId(id))}`,
    { method: "PUT", body, sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data ?? null, { status });
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const { data, status } = await frappeRequest<unknown>(
    `api/resource/Assessment Metric/${encodeURIComponent(decodeId(id))}`,
    { method: "DELETE", sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data ?? null, { status });
}
