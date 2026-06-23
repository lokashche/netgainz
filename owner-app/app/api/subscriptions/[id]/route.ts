import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Subscription } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const { data, status } = await frappeRequest<{ data: Subscription }>(
    `api/resource/Membership/${encodeURIComponent(id)}`,
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

  const { data, status } = await frappeRequest<{ data: Subscription }>(
    `api/resource/Membership/${encodeURIComponent(id)}`,
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
    `api/resource/Membership/${encodeURIComponent(id)}`,
    {
      method: "DELETE",
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
