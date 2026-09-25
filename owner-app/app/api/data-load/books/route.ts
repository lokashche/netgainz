import { NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";
import type { HistoryBooks } from "@/lib/types";

const BASE = "netgainz.net_gainz.loader.history_books";

// Stage 12.2: loaded history vs the books, month by month. Writes nothing.
export async function GET() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: HistoryBooks }>(
    `api/method/${BASE}.preview`,
    { sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}

// Post every postable history row. Runs in the background; the screen polls GET.
export async function POST() {
  const session = await getSession();
  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { data, status } = await frappeRequest<{ message: { status: string } }>(
    `api/method/${BASE}.post_history`,
    { method: "POST", sessionCookie: session.frappeCookies }
  );
  return NextResponse.json(data, { status });
}
