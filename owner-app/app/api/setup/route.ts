import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { SetupStatus } from "@/lib/types";

const BASE = "netgainz.net_gainz.onboarding";

// Stage 12.1: how far this gym is through setting up.
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: SetupStatus }>(
    `api/method/${BASE}.get_setup_status`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}

// Create the business (company, financial year, books). Runs in the background.
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const body = await req.json().catch(() => ({}));
  const { data, status } = await frappeRequest<{ message: { status: string } }>(
    `api/method/${BASE}.setup_business`,
    {
      method: "POST",
      body: JSON.stringify({
        company_name: body?.company_name ?? "",
        fy_start_month: body?.fy_start_month ?? 4,
        constitution: body?.constitution ?? "Proprietorship",
        gst_registered: body?.gst_registered ? 1 : 0,
        gstin: body?.gstin ?? "",
        bank_account: body?.bank_account ?? "",
      }),
      sessionCookie: session.frappeCookies,
    }
  );
  return NextResponse.json(data, { status });
}
