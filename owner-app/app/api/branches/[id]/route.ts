import { NextRequest, NextResponse } from "next/server";
import { decodeId, frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

// Rename, switch off / on, or make a branch the default.
export async function PUT(
  req: NextRequest,
  ctx: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await ctx.params;
  const body = await req.json().catch(() => ({}));
  const payload: Record<string, unknown> = { name: decodeId(id) };
  if (typeof body?.new_name === "string") payload.new_name = body.new_name;
  if (typeof body?.description === "string") payload.description = body.description;
  if (typeof body?.disabled === "boolean") payload.disabled = body.disabled ? 1 : 0;
  if (body?.make_default === true) payload.make_default = 1;

  const { data, status } = await frappeRequest<{ message: { name: string } }>(
    "api/method/netgainz.net_gainz.accounting.branch.update_branch",
    { method: "POST", body: JSON.stringify(payload), sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}
