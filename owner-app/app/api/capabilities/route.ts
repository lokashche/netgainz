import { NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { Capabilities } from "@/lib/types";

/**
 * WP-8: what the signed-in user is allowed to do.
 *
 * The backend guards every money endpoint by role, so this exists purely so the
 * UI can hide an action rather than let someone click a button that will only
 * come back 403. Gym Staff take payments; only the Gym Owner refunds or writes
 * off.
 */
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data, status } = await frappeRequest<{ message: Capabilities }>(
    "api/method/netgainz.net_gainz.permissions.get_my_capabilities",
    { sessionCookie: session.frappeCookies }
  );

  return NextResponse.json(data, { status });
}
