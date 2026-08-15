import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { DataLoadStep, DataLoadRunResult, DataLoadValidation } from "@/lib/types";

const STEPS = "netgainz.net_gainz.loader.data_load.get_steps";
const VALIDATE = "netgainz.net_gainz.loader.data_load.validate";
const RUN = "netgainz.net_gainz.loader.data_load.run";

/** The whole load, in order, with where each step has got to. */
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: DataLoadStep[] }>(
    `api/method/${STEPS}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}

/**
 * `?action=validate` reads the file and reports what would go wrong, writing
 * nothing — the dry run Frappe's Data Import does not have. `?action=run` loads it.
 */
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const action = req.nextUrl.searchParams.get("action") === "run" ? RUN : VALIDATE;
  const body = await req.text();

  const { data, status } = await frappeRequest<{
    message: DataLoadValidation | DataLoadRunResult;
  }>(`api/method/${action}`, {
    method: "POST",
    body,
    sessionCookie: session.frappeCookies,
  });
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
