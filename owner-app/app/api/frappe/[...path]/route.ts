import { NextRequest, NextResponse } from "next/server";
import { frappeRequest } from "@/lib/frappe";
import { getSession } from "@/lib/session";

type Params = { params: Promise<{ path: string[] }> };

async function handler(req: NextRequest, { params }: Params) {
  const session = await getSession();

  if (!session.frappeCookies) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { path } = await params;
  const frappeUrl = path.join("/");
  const searchParams = req.nextUrl.searchParams.toString();
  const fullPath = searchParams ? `${frappeUrl}?${searchParams}` : frappeUrl;

  const body = req.method !== "GET" ? await req.text() : undefined;

  const { data, status } = await frappeRequest(fullPath, {
    method: req.method,
    body,
    sessionCookie: session.frappeCookies,
  });

  return NextResponse.json(data, { status });
}

export { handler as GET, handler as POST, handler as PUT, handler as DELETE };
