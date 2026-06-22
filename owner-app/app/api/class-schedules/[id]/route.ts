import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { ClassSchedule } from "@/lib/types";

const GENERATE =
  "netgainz.net_gainz.doctype.class_schedule.class_schedule.generate_classes_now";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id: rawId } = await params;
  const id = decodeId(rawId);
  const { data, status } = await frappeRequest<{ data: ClassSchedule }>(
    `api/resource/Class Schedule/${encodeURIComponent(id)}`,
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}

export async function PUT(req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id: rawId } = await params;
  const id = decodeId(rawId);
  const body = await req.text();

  const { data, status } = await frappeRequest<{ data: ClassSchedule }>(
    `api/resource/Class Schedule/${encodeURIComponent(id)}`,
    { method: "PUT", body, sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}

// Generate this schedule's upcoming sessions now.
export async function POST(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id: rawId } = await params;
  const id = decodeId(rawId);
  const { data, status } = await frappeRequest<{ message: { created: number } }>(
    `api/method/${GENERATE}?name=${encodeURIComponent(id)}`,
    { method: "POST", sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data?.message ?? data, { status });
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id: rawId } = await params;
  const id = decodeId(rawId);
  const { data, status } = await frappeRequest(
    `api/resource/Class Schedule/${encodeURIComponent(id)}`,
    { method: "DELETE", sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}
