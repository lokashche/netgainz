import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

const BASE = "netgainz.net_gainz.staff_access";

// Change which branches a login may see, or switch it off / on.
export async function PUT(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await ctx.params;
  const user = decodeId(id);
  const body = await req.json().catch(() => ({}));

  let method: string;
  let payload: Record<string, unknown>;
  if (typeof body?.enabled === "boolean") {
    method = "set_staff_enabled";
    payload = { user, enabled: body.enabled ? 1 : 0 };
  } else {
    method = "set_staff_branches";
    payload = { user, branches: Array.isArray(body?.branches) ? body.branches : [] };
  }
  const { data, status } = await frappeRequest<{ message: unknown }>(`api/method/${BASE}.${method}`, {
    method: "POST",
    body: JSON.stringify(payload),
    sessionCookie: session.frappeCookies,
  });
  return NextResponse.json(data, { status });
}
