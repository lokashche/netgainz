import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { ClassSession } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const { data, status } = await frappeRequest<{ data: ClassSession }>(
    `api/resource/Session/${encodeURIComponent(id)}`,
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
  const body = await req.text();

  const { data, status } = await frappeRequest<{ data: ClassSession }>(
    `api/resource/Session/${encodeURIComponent(id)}`,
    {
      method: "PUT",
      body,
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const { data, status } = await frappeRequest(
    `api/resource/Session/${encodeURIComponent(id)}`,
    {
      method: "DELETE",
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
