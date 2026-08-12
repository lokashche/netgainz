import { NextRequest, NextResponse } from "next/server";
import { frappeRequest, decodeId } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { ConvertResult } from "@/lib/types";

const CONVERT = "netgainz.net_gainz.operations.enquiries.convert_to_member";

export async function POST(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  const { data, status } = await frappeRequest<{ message: ConvertResult }>(
    `api/method/${CONVERT}`,
    {
      method: "POST",
      body: JSON.stringify({ enquiry: decodeId(id) }),
      sessionCookie: session.frappeCookies,
    }
  );
  return NextResponse.json(data?.message ?? data ?? null, { status });
}
