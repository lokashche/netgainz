import { NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { ConversionBySource } from "@/lib/types";

const CONVERSION = "netgainz.net_gainz.operations.enquiries.conversion_by_source";

export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: ConversionBySource }>(
    `api/method/${CONVERSION}`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data?.message ?? null, { status });
}
