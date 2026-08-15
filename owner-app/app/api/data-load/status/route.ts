import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { DataLoadStep } from "@/lib/types";

const STATUS = "netgainz.net_gainz.loader.data_load.status";

/** Data Import runs as a background job, so the screen polls this. */
export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const step = req.nextUrl.searchParams.get("step") ?? "";
  const { data, status } = await frappeRequest<{ message: DataLoadStep }>(
    `api/method/${STATUS}?step_key=${encodeURIComponent(step)}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
