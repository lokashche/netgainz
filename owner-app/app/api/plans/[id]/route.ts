import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { MembershipPlan } from "@/lib/types";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id: rawId } = await params;
  const id = decodeId(rawId);
  const { data, status } = await frappeRequest<{ data: MembershipPlan }>(
    `api/resource/Membership Plan/${encodeURIComponent(id)}`,
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

  // A plan's name IS its document ID, so a changed name is a rename, not a
  // field update. The backend method moves the plan and its billing Item
  // together and repoints every membership that uses it.
  let target = id;
  let payload: Record<string, unknown> | null = null;
  try {
    payload = JSON.parse(body) as Record<string, unknown>;
  } catch {
    payload = null;
  }
  const newName =
    payload && typeof payload.plan_name === "string" ? payload.plan_name.trim() : "";
  if (newName && newName !== id) {
    const rename = await frappeRequest<{ message: string }>(
      "api/method/netgainz.net_gainz.accounting.provisioning.rename_plan",
      {
        method: "POST",
        body: JSON.stringify({ name: id, new_name: newName }),
        sessionCookie: session.frappeCookies,
      }
    );
    if (rename.status !== 200) {
      return NextResponse.json(rename.data ?? {}, { status: rename.status });
    }
    target = rename.data?.message ?? newName;
  }

  const { data, status } = await frappeRequest<{ data: MembershipPlan }>(
    `api/resource/Membership Plan/${encodeURIComponent(target)}`,
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

  const { id: rawId } = await params;
  const id = decodeId(rawId);
  const { data, status } = await frappeRequest(
    `api/resource/Membership Plan/${encodeURIComponent(id)}`,
    {
      method: "DELETE",
      sessionCookie: session.frappeCookies,
    }
  );

  return NextResponse.json(data, { status });
}
